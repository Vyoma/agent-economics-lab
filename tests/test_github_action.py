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


def csv_inputs(policy: Path | None = None, *, attested: bool = False) -> ActionInputs:
    """`attested=True` names the fixture instrument and supplies its
    calibration record, which a SCALE now requires on every shipped surface."""
    extra = (
        {
            "label_source": "fixture.manual-review",
            "attestations": str(EXAMPLES / "attestations.json"),
            "as_of": "2026-09-01",
        }
        if attested
        else {}
    )
    return ActionInputs(
        traces=str(EXAMPLES / "support_trace.csv"),
        outcomes=str(EXAMPLES / "outcomes.csv"),
        rates=str(EXAMPLES / "rates.json"),
        baseline=str(EXAMPLES / "baseline.json"),
        policy=str(policy or EXAMPLES / "policy.json"),
        **extra,
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
            result = run_action(csv_inputs(policy_path, attested=True), report)
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
                    attestations=str(EXAMPLES / "attestations.json"),
                    as_of="2026-09-01",
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
                    attestations=str(EXAMPLES / "attestations.json"),
                    as_of="2026-09-01",
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


class TheActionCanVerifyAClaim(unittest.TestCase):
    """Claim mode, and the guards that keep the two modes from colliding.

    The enforce step reads an exit code the evaluate step produces. Unguarded,
    a claim-mode run reached it with that variable unset and ran `exit ""`,
    which bash rejects with 255 -- failing closed, but with a code outside this
    action's documented set and no indication why.
    """

    #: Read as text, not parsed. This repository ships zero runtime
    #: dependencies and its dev extras are ruff and coverage; importing pyyaml
    #: here would have passed locally and raised ImportError in CI: a
    #: verification must run with only what the verifier will have.
    def setUp(self) -> None:
        self.metadata = (ROOT / "action.yml").read_text(encoding="utf-8")

    def _block(self, name: str) -> str:
        """The text of one step, from its name to the next step's dash."""
        start = self.metadata.index(f"- name: {name}")
        following = self.metadata.find("\n    - name: ", start + 1)
        return self.metadata[start : following if following != -1 else len(self.metadata)]

    def test_claim_is_an_input_and_verdict_is_an_output(self) -> None:
        self.assertIn("  claim:", self.metadata)
        self.assertIn("  verdict:", self.metadata)

    def test_the_two_modes_are_mutually_exclusive(self) -> None:
        self.assertIn("if: ${{ inputs.claim != '' }}", self._block("Verify a published claim"))
        self.assertIn("if: ${{ inputs.claim == '' }}", self._block("Evaluate economic assurance"))

    def test_every_step_reading_evaluate_output_is_guarded_to_that_mode(self) -> None:
        """A step consuming a skipped step's output must not run.

        Unguarded, claim mode reached the enforce step with
        AGENT_ECONOMICS_EXIT_CODE unset and ran `exit ""`, which bash rejects
        with 255: failing closed, but with a code outside this action's
        documented set.
        """
        for name in ("Upsert pull request report", "Enforce SCALE-only policy"):
            with self.subTest(step=name):
                block = self._block(name)
                self.assertTrue(
                    "steps.evaluate" in block
                    or "AGENT_ECONOMICS_EXIT_CODE" in block,
                    "this test guards the wrong step if it reads neither",
                )
                self.assertIn("inputs.claim == ''", block)

    def test_the_verify_step_maps_every_exit_code_to_a_verdict(self) -> None:
        script = self._block("Verify a published claim")
        for code, verdict in (("0", "SUPPORTED"), ("4", "REFUTED")):
            with self.subTest(code=code):
                self.assertIn(f"{code}) verdict={verdict}", script)
        self.assertIn("*) verdict=UNVERIFIED", script)
