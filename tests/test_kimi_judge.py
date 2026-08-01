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
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_economics import kimi_client
from agent_economics.kimi_judge import (
    _DEFAULT_MODEL,
    _DEFAULT_REASONING_EFFORT,
    _build_outcome_row,
    _build_system_prompt,
    _build_user_message,
    _error_outcome_row,
    _validate_rubric,
    _verdict_schema,
    judge,
    _main,
)

# Shaped like a real key. The client rejects short or templated values
# locally, so a fixture key must look plausible.
_FAKE_KEY = "sk-K3nQ7wZ2pR8sT1vY4bM6jL9cX0dF5gH2aN7eU3iO8kP1rW6z"

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
        out, audit = _build_outcome_row("t-001", _KIMI_ACCEPT, _RUBRIC, "kimi-k3")
        self.assertEqual(out["acceptable"], "true")
        self.assertEqual(out["business_value_usd"], "8.0")
        self.assertEqual(out["human_minutes"], "0")
        self.assertEqual(out["remediation_cost_usd"], "0")
        self.assertEqual(out["incident_loss_usd"], "0")

    def test_not_acceptable_row(self) -> None:
        out, audit = _build_outcome_row("t-002", _KIMI_REJECT, _RUBRIC, "kimi-k3")
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


class JudgePipelineTests(unittest.TestCase):
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

            with patch.dict("os.environ", {"MOONSHOT_API_KEY": _FAKE_KEY}):
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

            with patch.dict("os.environ", {"MOONSHOT_API_KEY": _FAKE_KEY}):
                judge(tasks_path, rubric_path, out_path, rate_limit=0)

            audit_path = tmp_dir / "outcomes.audit.json"
            self.assertTrue(audit_path.exists(), "audit sidecar not written")
            audit = json.loads(audit_path.read_text())
            self.assertEqual(len(audit), 1)
            self.assertEqual(audit[0]["task_id"], "t-001")

    @patch("agent_economics.kimi_client.BACKOFF_BASE_S", 0.0)
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

            with patch.dict("os.environ", {"MOONSHOT_API_KEY": _FAKE_KEY}):
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
            env_without_key = {k: v for k, v in __import__("os").environ.items()
                               if k != "MOONSHOT_API_KEY"}
            with patch.dict("os.environ", env_without_key, clear=True):
                with self.assertRaises(RuntimeError, msg="MOONSHOT_API_KEY"):
                    judge(tasks_path, rubric_path, out_path)

    def test_judge_raises_on_empty_task_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            tasks_path = tmp_dir / "empty.csv"
            tasks_path.write_text("task_id,output\n")
            rubric_path = self._write_rubric(tmp_dir)
            out_path = tmp_dir / "outcomes.csv"
            with patch.dict("os.environ", {"MOONSHOT_API_KEY": _FAKE_KEY}):
                with self.assertRaises(ValueError):
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
            with patch.dict("os.environ", {"MOONSHOT_API_KEY": _FAKE_KEY}):
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


class OutcomeCsvCompatibilityTests(unittest.TestCase):
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

            with patch.dict("os.environ", {"MOONSHOT_API_KEY": _FAKE_KEY}):
                judge(tasks_path, rubric_path, out_path, rate_limit=0)

            outcomes = load_outcomes(out_path)

        self.assertIn("t-001", outcomes)
        self.assertIn("t-002", outcomes)
        self.assertTrue(outcomes["t-001"].acceptable)
        self.assertFalse(outcomes["t-002"].acceptable)
        self.assertAlmostEqual(outcomes["t-001"].business_value_usd, 8.0)


class KimiRequestContractTests(unittest.TestCase):
    """The K3 request contract, per platform.kimi.ai/docs/api/chat."""

    def test_verdict_schema_is_strict_and_covers_every_criterion(self) -> None:
        response_format = _verdict_schema(_RUBRIC)
        self.assertEqual(response_format["type"], "json_schema")
        schema_wrapper = response_format["json_schema"]
        self.assertTrue(schema_wrapper["strict"])
        schema = schema_wrapper["schema"]
        self.assertFalse(schema["additionalProperties"])
        scores = schema["properties"]["criterion_scores"]
        self.assertEqual(
            sorted(scores["required"]),
            sorted(criterion["id"] for criterion in _RUBRIC["criteria"]),
        )
        self.assertFalse(scores["additionalProperties"])
        for name, spec in scores["properties"].items():
            with self.subTest(field=name):
                self.assertEqual(spec["type"], "number")

    def test_verdict_schema_carries_no_mfjs_rejected_keyword(self) -> None:
        """A range keyword here is a 400, not a constraint.

        Moonshot Flavored JSON Schema accepts only `type`, `enum`, and
        `required` for validation. Sending `minimum`/`maximum` returns HTTP 400,
        and because the judge falls back to an unacceptable label on error, that
        rejection would silently relabel every task.
        """
        kimi_client.assert_mfjs_compatible(_verdict_schema(_RUBRIC))
        blob = json.dumps(_verdict_schema(_RUBRIC))
        for keyword in kimi_client.MFJS_REJECTED_KEYWORDS:
            with self.subTest(keyword=keyword):
                self.assertNotIn(f'"{keyword}"', blob)

    def test_mfjs_guard_rejects_a_range_constrained_schema(self) -> None:
        """The guard must actually fire, and name the offending path."""
        bad = {
            "type": "json_schema",
            "json_schema": {
                "name": "v",
                "schema": {
                    "type": "object",
                    "properties": {
                        "overall_score": {"type": "number", "minimum": 0.0}
                    },
                },
            },
        }
        with self.assertRaises(ValueError) as caught:
            kimi_client.assert_mfjs_compatible(bad)
        self.assertIn("minimum", str(caught.exception))
        self.assertIn("overall_score", str(caught.exception))

    def test_out_of_range_score_is_rejected_after_parsing(self) -> None:
        """Bounds the schema cannot express are enforced in code."""
        from agent_economics.kimi_judge import _validate_verdict

        criteria = [criterion["id"] for criterion in _RUBRIC["criteria"]]
        valid = {
            "task_id": "t-001",
            "criterion_scores": {name: 0.9 for name in criteria},
            "overall_score": 0.9,
            "acceptable": True,
            "rationale": "ok",
        }
        _validate_verdict(valid, _RUBRIC)

        out_of_range = dict(valid["criterion_scores"])
        out_of_range[criteria[0]] = 2.0
        for field, mutated in (
            ("overall_score", {**valid, "overall_score": 1.4}),
            ("overall_score", {**valid, "overall_score": -0.1}),
            ("criterion_scores", {**valid, "criterion_scores": out_of_range}),
            (
                "criterion_scores",
                {**valid, "criterion_scores": {criteria[0]: 0.9}},
            ),
            (
                "criterion_scores",
                {
                    **valid,
                    "criterion_scores": {**valid["criterion_scores"], "extra": 0.5},
                },
            ),
            ("acceptable", {**valid, "acceptable": "yes"}),
            ("overall_score", {**valid, "overall_score": "high"}),
        ):
            with self.subTest(field=field, value=mutated.get(field)):
                with self.assertRaises(ValueError):
                    _validate_verdict(mutated, _RUBRIC)

    def test_token_budget_leaves_room_for_max_effort_reasoning(self) -> None:
        """K3 always reasons, and reasoning shares this budget."""
        from agent_economics import kimi_analyst
        from agent_economics.kimi_judge import _MAX_COMPLETION_TOKENS

        self.assertEqual(_DEFAULT_REASONING_EFFORT, "max")
        self.assertGreaterEqual(_MAX_COMPLETION_TOKENS, 16384)
        self.assertGreaterEqual(kimi_analyst._MAX_COMPLETION_TOKENS, 16384)

    @patch("agent_economics.kimi_client.urllib.request.urlopen")
    def test_payload_matches_the_k3_request_schema(self, mock_open: MagicMock) -> None:
        """K3 fixes sampling and renames the output-length field."""
        body = json.dumps(
            {"choices": [{"message": {"content": json.dumps({"acceptable": True})}}]}
        ).encode()
        mock_open.return_value.__enter__.return_value.read.return_value = body

        from agent_economics.kimi_judge import _call_kimi

        _call_kimi(
            "system",
            "user",
            api_key="k",
            model=_DEFAULT_MODEL,
            response_format=_verdict_schema(_RUBRIC),
        )
        request = mock_open.call_args[0][0]
        payload = json.loads(request.data)

        self.assertEqual(request.full_url, kimi_client.API_URL)
        self.assertEqual(payload["model"], "kimi-k3")
        self.assertEqual(payload["reasoning_effort"], _DEFAULT_REASONING_EFFORT)
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertIn("max_completion_tokens", payload)
        self.assertNotIn("max_tokens", payload)
        for fixed_server_side in ("temperature", "top_p", "presence_penalty",
                                  "frequency_penalty"):
            with self.subTest(field=fixed_server_side):
                self.assertNotIn(fixed_server_side, payload)

    def test_system_prompt_carries_no_per_task_content(self) -> None:
        """Context caching needs a stable prefix, so tasks stay in the user turn."""
        prompt = _build_system_prompt(_RUBRIC)
        user_message = _build_user_message("t-001", "the agent output", "ctx")
        self.assertNotIn("t-001", prompt)
        self.assertNotIn("the agent output", prompt)
        self.assertIn("t-001", user_message)
        self.assertIn("the agent output", user_message)

    @patch("agent_economics.kimi_client.BACKOFF_BASE_S", 0.0)
    @patch("agent_economics.kimi_client._post")
    def test_retryable_status_is_retried_then_succeeds(
        self, mock_post: MagicMock
    ) -> None:
        import urllib.error

        rate_limited = urllib.error.HTTPError(
            kimi_client.API_URL, 429, "Too Many Requests", {}, None
        )
        ok = {"choices": [{"message": {"content": '{"acceptable": true}'}}]}
        mock_post.side_effect = [rate_limited, rate_limited, ok]
        result = kimi_client.call_kimi_json(
            "system", "user", api_key="k", model=_DEFAULT_MODEL
        )
        self.assertEqual(result, {"acceptable": True})
        self.assertEqual(mock_post.call_count, 3)

    @patch("agent_economics.kimi_client.BACKOFF_BASE_S", 0.0)
    @patch("agent_economics.kimi_client._post")
    def test_non_retryable_status_fails_immediately(
        self, mock_post: MagicMock
    ) -> None:
        """A bad key must not be retried into a rate limit."""
        import urllib.error

        mock_post.side_effect = urllib.error.HTTPError(
            kimi_client.API_URL, 401, "Unauthorized", {}, None
        )
        with self.assertRaises(kimi_client.KimiRequestError) as caught:
            kimi_client.call_kimi("system", "user", api_key="k")
        self.assertEqual(caught.exception.status, 401)
        self.assertEqual(mock_post.call_count, 1)

    @patch("agent_economics.kimi_client._post")
    def test_rejected_request_aborts_instead_of_labelling(
        self, mock_post: MagicMock
    ) -> None:
        """The bug this guards: a 400 must not become 100% unacceptable.

        A rejected schema or bad key is a defect in the request, not a verdict.
        If judge() swallowed it, every task would be labeled unacceptable and the
        run would report a 0% acceptable_rate indistinguishable from real data.
        """
        import urllib.error

        mock_post.side_effect = urllib.error.HTTPError(
            kimi_client.API_URL, 400, "Bad Request", {}, None
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            tasks_path = tmp_dir / "tasks.csv"
            with open(tasks_path, "w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["task_id", "output"])
                writer.writeheader()
                writer.writerow({"task_id": "t-001", "output": "a"})
                writer.writerow({"task_id": "t-002", "output": "b"})
            rubric_path = tmp_dir / "rubric.json"
            rubric_path.write_text(json.dumps(_RUBRIC))
            out_path = tmp_dir / "outcomes.csv"

            with patch.dict("os.environ", {"MOONSHOT_API_KEY": _FAKE_KEY}):
                with self.assertRaises(kimi_client.KimiRequestError):
                    judge(tasks_path, rubric_path, out_path, rate_limit=0)

            self.assertFalse(
                out_path.exists(),
                "a rejected request must not produce an outcomes file",
            )

    def _run_judge_against_post(self, mock_post: MagicMock, verdict: dict) -> list[dict]:
        """Drive judge() through the real client with only the socket mocked."""
        mock_post.return_value = {
            "choices": [{"message": {"content": json.dumps(verdict)}}],
            "usage": {"completion_tokens": 40},
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            tasks_path = tmp_dir / "tasks.csv"
            with open(tasks_path, "w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["task_id", "output"])
                writer.writeheader()
                writer.writerow({"task_id": "t-001", "output": "a"})
            rubric_path = tmp_dir / "rubric.json"
            rubric_path.write_text(json.dumps(_RUBRIC))
            out_path = tmp_dir / "outcomes.csv"
            with patch.dict("os.environ", {"MOONSHOT_API_KEY": _FAKE_KEY}):
                judge(tasks_path, rubric_path, out_path, rate_limit=0)
            with open(out_path, newline="") as handle:
                return list(csv.DictReader(handle))

    @patch("agent_economics.kimi_client._post")
    def test_end_to_end_accepts_a_valid_verdict(self, mock_post: MagicMock) -> None:
        criteria = [criterion["id"] for criterion in _RUBRIC["criteria"]]
        rows = self._run_judge_against_post(
            mock_post,
            {
                "task_id": "t-001",
                "criterion_scores": {name: 0.95 for name in criteria},
                "overall_score": 0.95,
                "acceptable": True,
                "rationale": "ok",
            },
        )
        self.assertEqual(rows[0]["acceptable"], "true")

    @patch("agent_economics.kimi_client._post")
    def test_end_to_end_rejects_an_out_of_range_verdict(
        self, mock_post: MagicMock
    ) -> None:
        """An impossible score must fail the judgment, not enter the economics."""
        criteria = [criterion["id"] for criterion in _RUBRIC["criteria"]]
        rows = self._run_judge_against_post(
            mock_post,
            {
                "task_id": "t-001",
                "criterion_scores": {name: 7.0 for name in criteria},
                "overall_score": 7.0,
                "acceptable": True,
                "rationale": "impossible score",
            },
        )
        self.assertEqual(rows[0]["acceptable"], "false")

    @patch("agent_economics.kimi_client._post")
    def test_provider_error_message_is_surfaced(
        self, mock_post: MagicMock
    ) -> None:
        """The provider names the offending field; keep that in the message."""
        import io
        import urllib.error

        body = json.dumps(
            {"error": {"message": "invalid response_format: minimum not allowed"}}
        ).encode()
        mock_post.side_effect = urllib.error.HTTPError(
            kimi_client.API_URL, 400, "Bad Request", {}, io.BytesIO(body)
        )
        with self.assertRaises(kimi_client.KimiRequestError) as caught:
            kimi_client.call_kimi("system", "user", api_key="k")
        self.assertIn("minimum not allowed", str(caught.exception))

    @patch("agent_economics.kimi_client.BACKOFF_BASE_S", 0.0)
    @patch("agent_economics.kimi_client._post")
    def test_retries_are_bounded(self, mock_post: MagicMock) -> None:
        import urllib.error

        mock_post.side_effect = urllib.error.URLError("refused")
        with self.assertRaises(urllib.error.URLError):
            kimi_client.call_kimi("system", "user", api_key="k")
        self.assertEqual(mock_post.call_count, kimi_client.MAX_ATTEMPTS)

    @patch("agent_economics.kimi_client._post")
    def test_empty_content_is_an_error_not_a_verdict(
        self, mock_post: MagicMock
    ) -> None:
        mock_post.return_value = {
            "choices": [{"message": {"content": "  "}}],
            "usage": {"completion_tokens": 8192},
        }
        with self.assertRaises(RuntimeError):
            kimi_client.call_kimi("system", "user", api_key="k")

    def test_unknown_reasoning_effort_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            rubric_path = tmp_dir / "rubric.json"
            rubric_path.write_text(json.dumps(_RUBRIC))
            with patch.dict("os.environ", {"MOONSHOT_API_KEY": _FAKE_KEY}):
                with self.assertRaises(ValueError):
                    judge(
                        tmp_dir / "tasks.csv",
                        rubric_path,
                        tmp_dir / "outcomes.csv",
                        reasoning_effort="medium",
                    )

    @patch("agent_economics.kimi_judge._call_kimi")
    def test_audit_records_the_label_provenance(self, mock_call: MagicMock) -> None:
        """An assurance case needs to know how the label was produced."""
        mock_call.return_value = {
            "task_id": "t-001",
            "criterion_scores": {"accuracy": 1.0, "policy": 1.0, "tone": 1.0},
            "overall_score": 1.0,
            "acceptable": True,
            "rationale": "ok",
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            tasks_path = tmp_dir / "tasks.csv"
            with open(tasks_path, "w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["task_id", "output"])
                writer.writeheader()
                writer.writerow({"task_id": "t-001", "output": "Good."})
            rubric_path = tmp_dir / "rubric.json"
            rubric_path.write_text(json.dumps(_RUBRIC))
            out_path = tmp_dir / "outcomes.csv"
            with patch.dict("os.environ", {"MOONSHOT_API_KEY": _FAKE_KEY}):
                judge(
                    tasks_path,
                    rubric_path,
                    out_path,
                    rate_limit=0,
                    reasoning_effort="high",
                )
            audit = json.loads(
                (out_path.with_name("outcomes.audit.json")).read_text()
            )

        self.assertEqual(audit[0]["reasoning_effort"], "high")
        self.assertEqual(audit[0]["output_contract"], "json_schema/strict")
        self.assertEqual(audit[0]["model_id"], _DEFAULT_MODEL)


if __name__ == "__main__":
    unittest.main()
