"""
Conversion-contract readiness.

The field list here is a claim about what an operator must supply. It is only
correct if a real, working contract fills exactly all of it, and a fresh
template fills none of it. Both are asserted below against committed fixtures,
so the list cannot drift away from what the adapters actually require.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from agent_economics.cli import main
from agent_economics.models import Coverage
from agent_economics.readiness import REQUIRED_FIELDS, assess, assess_path, render_markdown

ROOT = Path(__file__).resolve().parents[1]
COMPLETE = ROOT / "examples" / "otel-genai" / "langfuse-conversion-contract.json"
CLAUDE_COMPLETE = ROOT / "examples" / "claude-code" / "conversion-contract.json"


class FieldInventoryTest(unittest.TestCase):
    def test_every_required_field_names_a_real_coverage_dimension(self) -> None:
        valid = {c for c in Coverage}
        for req in REQUIRED_FIELDS:
            with self.subTest(field=req.path):
                self.assertIn(req.coverage, valid)
                self.assertTrue(req.why.strip(), f"{req.path} has no explanation")

    def test_every_coverage_dimension_has_at_least_one_field(self) -> None:
        """A dimension no field feeds would be unreachable by any operator."""
        covered = {req.coverage for req in REQUIRED_FIELDS}
        self.assertEqual(covered, set(Coverage))


class CompletedContractsTest(unittest.TestCase):
    """A contract that really converts must satisfy every field claimed here."""

    def test_langfuse_contract_is_complete(self) -> None:
        report = assess_path(COMPLETE)
        self.assertTrue(report.ready, [g.field for g in report.gaps])
        self.assertEqual(len(report.filled), len(REQUIRED_FIELDS))

    def test_claude_code_contract_is_complete(self) -> None:
        report = assess_path(CLAUDE_COMPLETE)
        self.assertTrue(report.ready, [g.field for g in report.gaps])


class EmptyContractTest(unittest.TestCase):
    def test_nothing_supplied_blocks_every_dimension(self) -> None:
        report = assess({})
        self.assertFalse(report.ready)
        applicable = [r for r in REQUIRED_FIELDS if r.applies({})]
        self.assertEqual(len(report.gaps), len(applicable))
        self.assertEqual(set(report.blocked_coverage), {c.value for c in Coverage})
        self.assertEqual(report.to_dict()["would_return"], "INCOMPLETE")

    def test_blank_and_null_values_do_not_count_as_supplied(self) -> None:
        report = assess({"baseline": {"name": "", "acceptable_rate": None}})
        self.assertFalse(report.ready)
        fields = {g.field for g in report.gaps}
        self.assertIn("baseline.name", fields)
        self.assertIn("baseline.acceptable_rate", fields)

    def test_a_price_table_of_blanks_supplies_nothing(self) -> None:
        report = assess({"pricing": {"models": {"gpt-x": {"input_per_million_usd": None}}}})
        self.assertIn("pricing.models", {g.field for g in report.gaps})

    def test_tool_prices_are_only_required_when_the_agent_called_tools(self) -> None:
        """A trace with no tool calls cannot supply a tool price table."""
        without = assess({"source_inventory": {"tool_call_count": 0}})
        self.assertNotIn("pricing.tools", {g.field for g in without.gaps})
        with_tools = assess({"source_inventory": {"tool_call_count": 3}})
        self.assertIn("pricing.tools", {g.field for g in with_tools.gaps})

    def test_one_unlabelled_task_blocks_outcome_quality(self) -> None:
        """Every task must carry a label, not just the first."""
        doc = {"tasks": [{"acceptable": True}, {"acceptable": None}]}
        report = assess(doc)
        self.assertIn("tasks[].acceptable", {g.field for g in report.gaps})


class RenderTest(unittest.TestCase):
    def test_incomplete_report_names_the_blocked_coverage(self) -> None:
        text = render_markdown(assess({}))
        self.assertIn("INCOMPLETE", text)
        for coverage in Coverage:
            self.assertIn(coverage.value, text)

    def test_complete_report_gives_the_next_commands(self) -> None:
        text = render_markdown(assess_path(COMPLETE))
        self.assertIn("agent-economics convert", text)
        self.assertIn("agent-economics mutate", text)


class ContractStatusCliTest(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, str]:
        out = StringIO()
        with redirect_stdout(out), redirect_stderr(StringIO()):
            code = main(argv)
        return code, out.getvalue()

    def test_complete_contract_exits_zero_under_ci(self) -> None:
        code, _ = self._run(["contract-status", "--contract", str(COMPLETE), "--ci"])
        self.assertEqual(code, 0)

    def test_incomplete_contract_fails_closed_under_ci(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.json"
            path.write_text("{}")
            code, text = self._run(["contract-status", "--contract", str(path), "--ci"])
        self.assertEqual(code, 1)
        self.assertIn("INCOMPLETE", text)

    def test_json_output_is_machine_readable(self) -> None:
        code, text = self._run(
            ["contract-status", "--contract", str(COMPLETE), "--format", "json"]
        )
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(text)["ready"])

    def test_missing_file_fails_closed(self) -> None:
        code, _ = self._run(["contract-status", "--contract", "/nonexistent.json"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
