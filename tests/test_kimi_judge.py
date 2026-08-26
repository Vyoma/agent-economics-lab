"""
Tests for kimi_judge module.

All Kimi API calls are mocked — no network required. The tests verify:
  - Rubric validation logic
  - Prompt construction
  - Outcome row building (acceptable → correct CSV values)
  - Error fallback row (API failure → unacceptable, zeros)
  - Full judge() pipeline against temp files
  - CLI integration via main()
"""
from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_economics.kimi_judge import (
    _build_outcome_row,
    _build_system_prompt,
    _build_user_message,
    _error_outcome_row,
    _main,
    _validate_rubric,
    judge,
)

_RUBRIC = {
    "rubric_id": "test-v1",
    "task_type": "software support",
    "acceptable_threshold": 0.70,
    "business_value_usd_if_acceptable": 8.00,
    "human_minutes_if_not_acceptable": 8.0,
    "remediation_cost_usd_if_not_acceptable": 0.75,
    "incident_loss_usd_if_not_acceptable": 0.0,
    "criteria": [
        {"id": "accuracy", "question": "Was the answer correct?", "weight": 0.60},
        {"id": "tone", "question": "Was the tone professional?", "weight": 0.40},
    ],
}

_KIMI_ACCEPT = {
    "task_id": "t-001",
    "criterion_scores": {"accuracy": 0.9, "tone": 1.0},
    "overall_score": 0.94,
    "acceptable": True,
    "rationale": "Accurate and clear response.",
}

_KIMI_REJECT = {
    "task_id": "t-002",
    "criterion_scores": {"accuracy": 0.3, "tone": 0.6},
    "overall_score": 0.42,
    "acceptable": False,
    "rationale": "Incorrect information provided.",
}


class RubricValidationTests(unittest.TestCase):
    def test_valid_rubric_passes(self) -> None:
        _validate_rubric(_RUBRIC)  # should not raise

    def test_missing_field_raises(self) -> None:
        bad = {k: v for k, v in _RUBRIC.items() if k != "rubric_id"}
        with self.assertRaises(ValueError, msg="rubric_id"):
            _validate_rubric(bad)

    def test_empty_criteria_raises(self) -> None:
        bad = {**_RUBRIC, "criteria": []}
        with self.assertRaises(ValueError):
            _validate_rubric(bad)

    def test_weights_not_summing_to_one_raises(self) -> None:
        bad = {
            **_RUBRIC,
            "criteria": [
                {"id": "a", "question": "Q?", "weight": 0.4},
                {"id": "b", "question": "Q?", "weight": 0.4},
            ],
        }
        with self.assertRaises(ValueError, msg="weights"):
            _validate_rubric(bad)

    def test_criterion_missing_field_raises(self) -> None:
        bad = {
            **_RUBRIC,
            "criteria": [
                {"id": "a", "question": "Q?"},  # missing weight
            ],
        }
        with self.assertRaises(ValueError):
            _validate_rubric(bad)


class PromptBuildingTests(unittest.TestCase):
    def test_system_prompt_contains_threshold(self) -> None:
        prompt = _build_system_prompt(_RUBRIC)
        self.assertIn("0.7", prompt)
        self.assertIn("accuracy", prompt)
        self.assertIn("tone", prompt)

    def test_system_prompt_json_keys(self) -> None:
        prompt = _build_system_prompt(_RUBRIC)
        self.assertIn('"accuracy"', prompt)
        self.assertIn('"tone"', prompt)

    def test_user_message_contains_task_id(self) -> None:
        msg = _build_user_message("t-001", "The answer is 42.", "context here")
        self.assertIn("t-001", msg)
        self.assertIn("42", msg)
        self.assertIn("context here", msg)

    def test_user_message_without_context(self) -> None:
        msg = _build_user_message("t-002", "output text", "")
        self.assertIn("t-002", msg)
        self.assertNotIn("context:", msg)


class OutcomeRowTests(unittest.TestCase):
    def test_acceptable_row(self) -> None:
        out, _audit = _build_outcome_row("t-001", _KIMI_ACCEPT, _RUBRIC, "kimi-k3")
        self.assertEqual(out["acceptable"], "true")
        self.assertEqual(out["business_value_usd"], "8.0")
        self.assertEqual(out["human_minutes"], "0")
        self.assertEqual(out["remediation_cost_usd"], "0")
        self.assertEqual(out["incident_loss_usd"], "0")

    def test_not_acceptable_row(self) -> None:
        out, _audit = _build_outcome_row("t-002", _KIMI_REJECT, _RUBRIC, "kimi-k3")
        self.assertEqual(out["acceptable"], "false")
        self.assertEqual(out["business_value_usd"], "0")
        self.assertEqual(out["human_minutes"], "8.0")
        self.assertEqual(out["remediation_cost_usd"], "0.75")
        self.assertEqual(out["incident_loss_usd"], "0.0")

    def test_audit_row_contains_scores(self) -> None:
        _, audit = _build_outcome_row("t-001", _KIMI_ACCEPT, _RUBRIC, "kimi-k3")
        self.assertAlmostEqual(audit["overall_score"], 0.94)
        self.assertIn("accuracy", audit["criterion_scores"])
        self.assertEqual(audit["rubric_id"], "test-v1")
        self.assertIn("kimi-judge@", audit["label_source"])

    def test_acceptable_value_is_lowercase(self) -> None:
        out_true, _ = _build_outcome_row("t-001", _KIMI_ACCEPT, _RUBRIC, "kimi-k3")
        out_false, _ = _build_outcome_row("t-002", _KIMI_REJECT, _RUBRIC, "kimi-k3")
        # framework's load_outcomes() accepts "true"/"false" (lowercase only)
        self.assertEqual(out_true["acceptable"], "true")
        self.assertEqual(out_false["acceptable"], "false")


class ErrorRowTests(unittest.TestCase):
    def test_error_row_counts_as_unacceptable(self) -> None:
        out, audit = _error_outcome_row("t-fail", _RUBRIC, "timeout")
        self.assertEqual(out["acceptable"], "false")
        self.assertEqual(out["business_value_usd"], "0")
        self.assertIn("timeout", audit["rationale"])
        self.assertEqual(audit["model_id"], "error")

    def test_error_row_zeros_out_costs(self) -> None:
        out, _ = _error_outcome_row("t-fail", _RUBRIC, "network error")
        self.assertEqual(out["human_minutes"], "0")
        self.assertEqual(out["remediation_cost_usd"], "0")
        self.assertEqual(out["incident_loss_usd"], "0")


class _QuietStdout(unittest.TestCase):
    """
    Base case that captures stdout for the duration of each test.

    The CLI and judge pipelines print their reports by design. Letting that
    reach the terminal buries the unittest summary under hundreds of lines, so
    the output is captured and left available on ``self.stdout`` for assertions.
    """

    def setUp(self) -> None:
        super().setUp()
        self.stdout = io.StringIO()
        redirect = redirect_stdout(self.stdout)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)


class JudgePipelineTests(_QuietStdout):
    def _write_tasks(self, tmp_dir: Path) -> Path:
        tasks_path = tmp_dir / "tasks.csv"
        with open(tasks_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["task_id", "output", "context"])
            writer.writeheader()
            writer.writerow({"task_id": "t-001", "output": "Great answer.", "context": "Q1"})
            writer.writerow({"task_id": "t-002", "output": "Wrong answer.", "context": "Q2"})
        return tasks_path

    def _write_rubric(self, tmp_dir: Path) -> Path:
        rubric_path = tmp_dir / "rubric.json"
        rubric_path.write_text(json.dumps(_RUBRIC))
        return rubric_path

    @patch("agent_economics.kimi_judge._call_kimi")
    def test_judge_writes_outcomes_csv(self, mock_call: MagicMock) -> None:
        mock_call.side_effect = [
            {**_KIMI_ACCEPT, "task_id": "t-001"},
            {**_KIMI_REJECT, "task_id": "t-002"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            tasks_path = self._write_tasks(tmp_dir)
            rubric_path = self._write_rubric(tmp_dir)
            out_path = tmp_dir / "outcomes.csv"

            with patch.dict("os.environ", {"MOONSHOT_API_KEY": "test-key"}):
                judge(tasks_path, rubric_path, out_path, rate_limit=0)

            with open(out_path, newline="") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["task_id"], "t-001")
        self.assertEqual(rows[0]["acceptable"], "true")
        self.assertEqual(rows[1]["task_id"], "t-002")
        self.assertEqual(rows[1]["acceptable"], "false")

    @patch("agent_economics.kimi_judge._call_kimi")
    def test_judge_writes_audit_sidecar(self, mock_call: MagicMock) -> None:
        mock_call.return_value = {**_KIMI_ACCEPT, "task_id": "t-001"}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            tasks_path = tmp_dir / "tasks.csv"
            with open(tasks_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["task_id", "output"])
                w.writeheader()
                w.writerow({"task_id": "t-001", "output": "OK."})
            rubric_path = self._write_rubric(tmp_dir)
            out_path = tmp_dir / "outcomes.csv"

            with patch.dict("os.environ", {"MOONSHOT_API_KEY": "test-key"}):
                judge(tasks_path, rubric_path, out_path, rate_limit=0)

            audit_path = tmp_dir / "outcomes.audit.json"
            self.assertTrue(audit_path.exists(), "audit sidecar not written")
            audit = json.loads(audit_path.read_text())
            self.assertEqual(len(audit), 1)
            self.assertEqual(audit[0]["task_id"], "t-001")

    @patch("agent_economics.kimi_judge._call_kimi")
    def test_judge_fallback_on_api_error(self, mock_call: MagicMock) -> None:
        import urllib.error
        mock_call.side_effect = urllib.error.URLError("connection refused")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            tasks_path = tmp_dir / "tasks.csv"
            with open(tasks_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["task_id", "output"])
                w.writeheader()
                w.writerow({"task_id": "t-err", "output": "output"})
            rubric_path = self._write_rubric(tmp_dir)
            out_path = tmp_dir / "outcomes.csv"

            with patch.dict("os.environ", {"MOONSHOT_API_KEY": "test-key"}):
                judge(tasks_path, rubric_path, out_path, rate_limit=0)

            with open(out_path, newline="") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(rows[0]["acceptable"], "false")

    def test_judge_raises_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            tasks_path = self._write_tasks(tmp_dir)
            rubric_path = self._write_rubric(tmp_dir)
            out_path = tmp_dir / "outcomes.csv"
            env_without_key = {
                k: v for k, v in os.environ.items() if k != "MOONSHOT_API_KEY"
            }
            with (
                patch.dict("os.environ", env_without_key, clear=True),
                self.assertRaises(RuntimeError, msg="MOONSHOT_API_KEY"),
            ):
                judge(tasks_path, rubric_path, out_path)

    def test_judge_raises_on_empty_task_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            tasks_path = tmp_dir / "empty.csv"
            tasks_path.write_text("task_id,output\n")
            rubric_path = self._write_rubric(tmp_dir)
            out_path = tmp_dir / "outcomes.csv"
            with (
                patch.dict("os.environ", {"MOONSHOT_API_KEY": "test-key"}),
                self.assertRaises(ValueError),
            ):
                judge(tasks_path, rubric_path, out_path)

    @patch("agent_economics.kimi_judge._call_kimi")
    def test_cli_main_returns_zero(self, mock_call: MagicMock) -> None:
        mock_call.return_value = {**_KIMI_ACCEPT, "task_id": "t-001"}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            tasks_path = tmp_dir / "tasks.csv"
            with open(tasks_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["task_id", "output"])
                w.writeheader()
                w.writerow({"task_id": "t-001", "output": "OK."})
            rubric_path = self._write_rubric(tmp_dir)
            out_path = tmp_dir / "outcomes.csv"
            with patch.dict("os.environ", {"MOONSHOT_API_KEY": "test-key"}):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = _main([
                        "--task-results", str(tasks_path),
                        "--rubric", str(rubric_path),
                        "--out", str(out_path),
                        "--rate-limit", "0",
                    ])
        self.assertEqual(code, 0)
        self.assertIn("1 acceptable", buf.getvalue())


class OutcomeCsvCompatibilityTests(_QuietStdout):
    """Ensure judge output is compatible with load_outcomes() from the framework."""

    @patch("agent_economics.kimi_judge._call_kimi")
    def test_outcomes_loadable_by_framework(self, mock_call: MagicMock) -> None:
        from agent_economics import load_outcomes

        mock_call.side_effect = [
            {**_KIMI_ACCEPT, "task_id": "t-001"},
            {**_KIMI_REJECT, "task_id": "t-002"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            tasks_path = tmp_dir / "tasks.csv"
            with open(tasks_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["task_id", "output"])
                w.writeheader()
                w.writerow({"task_id": "t-001", "output": "Good."})
                w.writerow({"task_id": "t-002", "output": "Bad."})
            rubric_path = tmp_dir / "rubric.json"
            rubric_path.write_text(json.dumps(_RUBRIC))
            out_path = tmp_dir / "outcomes.csv"

            with patch.dict("os.environ", {"MOONSHOT_API_KEY": "test-key"}):
                judge(tasks_path, rubric_path, out_path, rate_limit=0)

            outcomes = load_outcomes(out_path)

        self.assertIn("t-001", outcomes)
        self.assertIn("t-002", outcomes)
        self.assertTrue(outcomes["t-001"].acceptable)
        self.assertFalse(outcomes["t-002"].acceptable)
        self.assertAlmostEqual(outcomes["t-001"].business_value_usd, 8.0)


if __name__ == "__main__":
    unittest.main()
