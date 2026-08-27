from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from agent_economics.github_action import ActionInputs, main, run_action

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def csv_inputs(policy: Path | None = None) -> ActionInputs:
    return ActionInputs(
        traces=str(EXAMPLES / "support_trace.csv"),
        outcomes=str(EXAMPLES / "outcomes.csv"),
        rates=str(EXAMPLES / "rates.json"),
        baseline=str(EXAMPLES / "baseline.json"),
        policy=str(policy or EXAMPLES / "policy.json"),
    )


class GitHubActionTests(unittest.TestCase):
    def test_csv_mode_propagates_assist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            result = run_action(csv_inputs(), report)
            rendered = report.read_text(encoding="utf-8")
        self.assertEqual(result.decision, "ASSIST")
        self.assertEqual(result.exit_code, 3)
        self.assertIn("**Decision: ASSIST**", rendered)

    def test_only_scale_returns_zero(self) -> None:
        policy = json.loads(
            (EXAMPLES / "policy.json").read_text(encoding="utf-8")
        )
        policy.update(
            {
                "min_acceptable_rate": 0.70,
                "max_cost_per_acceptable_outcome_usd": 4.00,
                "max_p95_task_cost_usd": 20.00,
                "max_trace_cost_per_task_usd": 20.00,
                "max_calls_per_task": 20,
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            policy_path = Path(directory) / "scale-policy.json"
            policy_path.write_text(
                json.dumps(policy, sort_keys=True),
                encoding="utf-8",
            )
            report = Path(directory) / "report.md"
            result = run_action(csv_inputs(policy_path), report)
            rendered = report.read_text(encoding="utf-8")
        self.assertEqual(result.decision, "SCALE")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("**Decision: SCALE**", rendered)

    def test_stop_remains_a_failing_exit_code(self) -> None:
        policy = json.loads(
            (EXAMPLES / "policy.json").read_text(encoding="utf-8")
        )
        policy["min_expected_net_value_per_attempt_usd"] = 100.0
        with tempfile.TemporaryDirectory() as directory:
            policy_path = Path(directory) / "stop-policy.json"
            policy_path.write_text(
                json.dumps(policy, sort_keys=True),
                encoding="utf-8",
            )
            report = Path(directory) / "report.md"
            result = run_action(csv_inputs(policy_path), report)
        self.assertEqual(result.decision, "STOP")
        self.assertEqual(result.exit_code, 4)

    def test_adapter_mode_matches_checked_in_assurance_case(self) -> None:
        fixture = EXAMPLES / "claude-code"
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            result = run_action(
                ActionInputs(
                    adapter="claude-code",
                    session=str(fixture / "session.jsonl"),
                    contract=str(fixture / "conversion-contract.json"),
                ),
                report,
            )
            rendered = report.read_text(encoding="utf-8")
        self.assertEqual(result.decision, "ASSIST")
        self.assertEqual(result.exit_code, 3)
        self.assertEqual(
            rendered,
            (fixture / "assurance-case.md").read_text(encoding="utf-8"),
        )

    def test_otel_adapter_mode_propagates_scale(self) -> None:
        fixture = EXAMPLES / "otel-genai"
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            result = run_action(
                ActionInputs(
                    adapter="otel-genai",
                    session=str(fixture / "langfuse-otlp.json"),
                    contract=str(
                        fixture / "langfuse-conversion-contract.json"
                    ),
                ),
                report,
            )
            rendered = report.read_text(encoding="utf-8")
        self.assertEqual(result.decision, "SCALE")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("**Decision: SCALE**", rendered)

    def test_claude_code_tree_adapter_mode_propagates_scale(self) -> None:
        fixture = EXAMPLES / "claude-code-tree"
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            result = run_action(
                ActionInputs(
                    adapter="claude-code-tree",
                    session=str(fixture / "session.jsonl"),
                    contract=str(fixture / "conversion-contract.json"),
                ),
                report,
            )
            rendered = report.read_text(encoding="utf-8")
        self.assertEqual(result.decision, "SCALE")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            rendered,
            (fixture / "assurance-case.md").read_text(encoding="utf-8"),
        )

    def test_partial_or_conflicting_inputs_fail_closed(self) -> None:
        cases = (
            ActionInputs(traces="traces.csv"),
            ActionInputs(
                bundle="bundle.json",
                traces="traces.csv",
                outcomes="outcomes.csv",
                rates="rates.json",
                baseline="baseline.json",
                policy="policy.json",
            ),
            ActionInputs(
                adapter="future-vendor",
                session="session.jsonl",
                contract="contract.json",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, inputs in enumerate(cases):
                with self.subTest(inputs=inputs):
                    report = Path(directory) / f"report-{index}.md"
                    result = run_action(inputs, report)
                    self.assertEqual(result.decision, "INCOMPLETE")
                    self.assertEqual(result.exit_code, 2)
                    self.assertIn(
                        "**Decision: INCOMPLETE**",
                        report.read_text(encoding="utf-8"),
                    )

    def test_action_entrypoint_emits_outputs_without_hiding_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "github-output"
            report_path = Path(directory) / "report.md"
            with patch.dict(
                os.environ,
                {"GITHUB_OUTPUT": str(output_path)},
                clear=False,
            ), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                process_code = main(
                    [
                        "--traces",
                        str(EXAMPLES / "support_trace.csv"),
                        "--outcomes",
                        str(EXAMPLES / "outcomes.csv"),
                        "--rates",
                        str(EXAMPLES / "rates.json"),
                        "--baseline",
                        str(EXAMPLES / "baseline.json"),
                        "--policy",
                        str(EXAMPLES / "policy.json"),
                        "--report",
                        str(report_path),
                    ]
                )
            outputs = output_path.read_text(encoding="utf-8")
        self.assertEqual(process_code, 0)
        self.assertIn("decision<<", outputs)
        self.assertIn("\nASSIST\n", outputs)
        self.assertIn("exit-code<<", outputs)
        self.assertIn("\n3\n", outputs)
        self.assertIn(str(report_path), outputs)

    def test_action_metadata_declares_three_modes_and_scale_enforcement(self) -> None:
        metadata = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertIn("using: composite", metadata)
        self.assertIn("bundle:", metadata)
        self.assertIn("traces:", metadata)
        self.assertIn("adapter:", metadata)
        self.assertIn("actions/github-script@v9", metadata)
        self.assertIn('run: exit "$AGENT_ECONOMICS_EXIT_CODE"', metadata)


if __name__ == "__main__":
    unittest.main()
