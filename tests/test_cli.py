from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from agent_economics.cli import main


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


class CliTests(unittest.TestCase):
    def test_capabilities_lists_real_components(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["capabilities"])
        self.assertEqual(exit_code, 0)
        self.assertIn("source.normalized-json@1", output.getvalue())
        self.assertIn("gate.counterfactual@1", output.getvalue())
        self.assertIn("renderer.json@1", output.getvalue())

    def test_json_output_is_machine_readable(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "evaluate",
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
                    "--format",
                    "json",
                ]
            )
        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["decision"], "ASSIST")
        self.assertEqual(payload["renderer"], "renderer.json@1")
        self.assertEqual(payload["manifest"]["missing_coverage"], [])

    def test_ci_exit_code_encodes_assist(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "evaluate",
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
                    "--format",
                    "json",
                    "--ci",
                ]
            )
        self.assertEqual(exit_code, 3)

    def test_frontier_verification_cannot_overwrite_itself(self) -> None:
        error = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "frontier.md"
            artifact.write_text("stale\n", encoding="utf-8")
            with redirect_stderr(error):
                exit_code = main(
                    [
                        "frontier",
                        str(EXAMPLES / "compute-frontier" / "manifest.json"),
                        "--output-dir",
                        directory,
                        "--verify-dir",
                        directory,
                    ]
                )
            self.assertEqual(artifact.read_text(encoding="utf-8"), "stale\n")
        self.assertEqual(exit_code, 2)
        self.assertIn("must be different", error.getvalue())


if __name__ == "__main__":
    unittest.main()
