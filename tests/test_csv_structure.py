"""Malformed CSV must not silently discard or fabricate economic evidence."""
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from agent_economics.cli import main
from agent_economics.io import load_dependency_edges, load_outcomes, load_traces


class CsvStructureTests(unittest.TestCase):
    def test_cli_refuses_truncated_costs_without_emitting_a_decision(self):
        examples = Path(__file__).resolve().parents[1] / "examples"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "outcomes.csv"
            path.write_text(
                "task_id,acceptable,business_value_usd,human_minutes,"
                "remediation_cost_usd,incident_loss_usd\nt1,true,10,0\n",
                encoding="utf-8",
            )
            args = ["evaluate", "--outcomes", str(path)]
            for flag, name in [("traces", "support_trace.csv"), ("rates", "rates.json"),
                               ("baseline", "baseline.json"), ("policy", "policy.json")]:
                args.extend([f"--{flag}", str(examples / name)])
            output, errors = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                result = main(args)
            self.assertEqual(result, 2)
            self.assertEqual(output.getvalue(), "")
            self.assertIn("INCOMPLETE: invalid evidence: CSV", errors.getvalue())

    def test_quoted_multiline_fields_remain_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.csv"
            path.write_text(
                'task_id,event_id,event_type,name\nt1,e1,llm,"name, with\nnewline"\n',
                encoding="utf-8",
            )
            self.assertEqual(load_traces(path)[0].name, "name, with\nnewline")

    def test_malformed_rows_are_refused(self):
        cases = [
            (load_outcomes,
             "task_id,acceptable,business_value_usd,human_minutes,"
             "remediation_cost_usd,incident_loss_usd\nt1,true,10,0\n"),
            (load_outcomes,
             "task_id,acceptable,business_value_usd,human_minutes,"
             "remediation_cost_usd,incident_loss_usd,incident_loss_usd\n"
             "t1,true,10,0,0,1000,0\n"),
            (load_outcomes,
             "task_id,acceptable,business_value_usd,human_minutes,"
             "remediation_cost_usd,incident_loss_usd\nt1,true,10,0,0,0,1000\n"),
            (load_traces, "task_id,event_id,event_type,name,direct_cost_usd\nt1,e1,llm,m\n"),
            (load_dependency_edges, "event_id,parent_event_id\ne1\n"),
            (load_traces, "task_id,event_id,event_type,name\nt1,e1,llm,\"unterminated\n"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            for loader, content in cases:
                with self.subTest(loader=loader.__name__, content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "CSV"):
                        loader(path)

    def test_explicit_empty_cells_keep_existing_zero_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text(
                "task_id,acceptable,business_value_usd,human_minutes,"
                "remediation_cost_usd,incident_loss_usd\nt1,true,10,,,\n",
                encoding="utf-8",
            )
            self.assertEqual(load_outcomes(path)["t1"].incident_loss_usd, 0)


if __name__ == "__main__":
    unittest.main()
