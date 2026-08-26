"""
Tests for the kimi_analyst module and the `analyse` CLI subcommand.

The network call is always mocked: no test may reach api.moonshot.ai.
"""
from __future__ import annotations

import json
import os
import tempfile
import typing
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from agent_economics import evaluate_bundle, load_normalized_json_bundle
from agent_economics.cli import main
from agent_economics.kimi_analyst import (
    AnalysisResult,
    Fix,
    _build_context_from_case,
    _build_context_from_report,
    _get_api_key,
    _main,
    _parse_result,
    analyse,
    analyse_report,
)

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "examples" / "claude-code" / "bundle.json"

KIMI_PAYLOAD = {
    "decision": "ASSIST",
    "summary": "Outcome quality is the sole blocker.",
    "fixes": [
        {
            "rank": 1,
            "gate": "gate.outcome-quality",
            "gap": "50% observed vs 80% required",
            "action": "Add a retrieval step before drafting.",
            "effort": "medium",
            "expected_impact": "+20pp acceptable rate",
        },
        {
            "rank": 2,
            "gate": "gate.unit-economics",
            "gap": "$0.90 vs $1.00",
            "action": "Route short tasks to a cheaper model.",
            "effort": "low",
            "expected_impact": "-15% cost per acceptable outcome",
        },
    ],
    "viability": {"recoverable": True, "break_even_notes": "Needs +1 acceptable task."},
    "watch_outs": ["p95 cost is within 10% of the cap."],
    "revised_policy": {"min_acceptable_rate": 0.7},
}


def _evaluated_case():
    return evaluate_bundle(load_normalized_json_bundle(BUNDLE))


class ParseResultTest(unittest.TestCase):
    def test_parses_a_full_payload(self) -> None:
        result = _parse_result(KIMI_PAYLOAD, "kimi-k3")
        self.assertEqual(result.decision, "ASSIST")
        self.assertEqual(result.model_id, "kimi-k3")
        self.assertEqual(len(result.fixes), 2)
        self.assertEqual(result.fixes[0].gate, "gate.outcome-quality")
        self.assertTrue(result.viability_recoverable)
        self.assertEqual(result.watch_outs, ["p95 cost is within 10% of the cap."])
        self.assertEqual(result.revised_policy, {"min_acceptable_rate": 0.7})

    def test_empty_payload_degrades_without_raising(self) -> None:
        """A malformed model response must not crash the caller."""
        result = _parse_result({}, "kimi-k3")
        self.assertEqual(result.decision, "UNKNOWN")
        self.assertEqual(result.summary, "")
        self.assertEqual(result.fixes, [])
        self.assertIsNone(result.viability_recoverable)
        self.assertEqual(result.watch_outs, [])
        self.assertEqual(result.revised_policy, {})

    def test_null_collections_are_treated_as_empty(self) -> None:
        result = _parse_result(
            {"fixes": None, "watch_outs": None, "revised_policy": None, "viability": None},
            "kimi-k3",
        )
        self.assertEqual(result.fixes, [])
        self.assertEqual(result.watch_outs, [])
        self.assertEqual(result.revised_policy, {})

    def test_missing_fix_fields_fall_back_to_defaults(self) -> None:
        result = _parse_result({"fixes": [{}, {}]}, "kimi-k3")
        self.assertEqual([f.rank for f in result.fixes], [1, 2])
        self.assertEqual(result.fixes[0].effort, "medium")


class AnalysisResultTest(unittest.TestCase):
    def test_to_dict_round_trips_through_json(self) -> None:
        result = _parse_result(KIMI_PAYLOAD, "kimi-k3")
        payload = json.loads(json.dumps(result.to_dict()))
        self.assertEqual(payload["decision"], "ASSIST")
        self.assertEqual(payload["model_id"], "kimi-k3")
        self.assertEqual(len(payload["fixes"]), 2)
        self.assertTrue(payload["viability"]["recoverable"])

    def test_render_markdown_names_the_decision_and_every_fix(self) -> None:
        markdown = _parse_result(KIMI_PAYLOAD, "kimi-k3").render_markdown()
        self.assertIn("**Decision: ASSIST**", markdown)
        for fix in KIMI_PAYLOAD["fixes"]:
            self.assertIn(fix["gate"], markdown)

    def test_render_markdown_handles_an_empty_result(self) -> None:
        self.assertIn("UNKNOWN", AnalysisResult(decision="UNKNOWN", summary="").render_markdown())

    def test_fix_is_constructible_directly(self) -> None:
        fix = Fix(rank=1, gate="g", gap="x", action="a", effort="low", expected_impact="i")
        self.assertEqual(fix.rank, 1)


class ContextBuilderTest(unittest.TestCase):
    """The context string is what the model actually sees."""

    def test_case_context_carries_the_decision_and_task_counts(self) -> None:
        case = _evaluated_case()
        context = _build_context_from_case(case, None, None)
        self.assertIn("ASSURANCE CASE SUMMARY", context)
        self.assertIn(case.decision.value, context)
        self.assertIn(f"{len(case.tasks)} attempts", context)

    def test_case_context_accepts_policy_and_baseline(self) -> None:
        bundle = load_normalized_json_bundle(BUNDLE)
        case = evaluate_bundle(bundle)
        context = _build_context_from_case(case, bundle.policy, bundle.baseline)
        self.assertIn(case.decision.value, context)
        self.assertGreater(len(context), len(_build_context_from_case(case, None, None)))

    def test_report_context_matches_the_evaluate_json_shape(self) -> None:
        report = {
            "decision": "STOP",
            "metrics": {"attempts": 10, "acceptable_rate": 0.4},
        }
        context = _build_context_from_report(report, None, None)
        self.assertIn("STOP", context)
        self.assertIn("10 attempts", context)
        self.assertIn("4 acceptable", context)

    def test_report_context_tolerates_an_empty_report(self) -> None:
        context = _build_context_from_report({}, None, None)
        self.assertIn("UNKNOWN", context)


class ApiKeyTest(unittest.TestCase):
    def test_missing_key_raises_with_actionable_text(self) -> None:
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError) as ctx:
            _get_api_key()
        self.assertIn("MOONSHOT_API_KEY", str(ctx.exception))

    def test_present_key_is_returned(self) -> None:
        with patch.dict(os.environ, {"MOONSHOT_API_KEY": "sk-test"}, clear=True):
            self.assertEqual(_get_api_key(), "sk-test")


class AnalyseTest(unittest.TestCase):
    """The two public entry points, with the network call mocked out."""

    @patch("agent_economics.kimi_analyst._call_kimi_analyst")
    def test_analyse_returns_a_parsed_result(self, mock_call) -> None:
        mock_call.return_value = KIMI_PAYLOAD
        with patch.dict(os.environ, {"MOONSHOT_API_KEY": "sk-test"}, clear=True):
            result = analyse(_evaluated_case())
        self.assertEqual(result.decision, "ASSIST")
        self.assertEqual(len(result.fixes), 2)
        mock_call.assert_called_once()

    @patch("agent_economics.kimi_analyst._call_kimi_analyst")
    def test_analyse_report_returns_a_parsed_result(self, mock_call) -> None:
        mock_call.return_value = KIMI_PAYLOAD
        report = {"decision": "ASSIST", "metrics": {"attempts": 2, "acceptable_rate": 0.5}}
        with patch.dict(os.environ, {"MOONSHOT_API_KEY": "sk-test"}, clear=True):
            result = analyse_report(report)
        self.assertEqual(result.decision, "ASSIST")

    def test_analyse_refuses_without_an_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            analyse(_evaluated_case())

    @patch("agent_economics.kimi_analyst._call_kimi_analyst")
    def test_model_override_is_passed_through(self, mock_call) -> None:
        mock_call.return_value = KIMI_PAYLOAD
        with patch.dict(os.environ, {"MOONSHOT_API_KEY": "sk-test"}, clear=True):
            result = analyse(_evaluated_case(), model="kimi-custom")
        self.assertEqual(result.model_id, "kimi-custom")
        self.assertEqual(mock_call.call_args.kwargs["model"], "kimi-custom")


class AnalyseCliTest(unittest.TestCase):
    """`agent-economics analyse` and the module's own argv entry point."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.case_path = Path(self.tmp.name) / "report.json"
        self.case_path.write_text(
            json.dumps({"decision": "ASSIST", "metrics": {"attempts": 2, "acceptable_rate": 0.5}})
        )

    @patch("agent_economics.kimi_analyst._call_kimi_analyst")
    def test_markdown_output(self, mock_call) -> None:
        mock_call.return_value = KIMI_PAYLOAD
        out = StringIO()
        with (
            patch.dict(os.environ, {"MOONSHOT_API_KEY": "sk-test"}, clear=True),
            redirect_stdout(out),
            redirect_stderr(StringIO()),
        ):
                code = main(["analyse", "--case", str(self.case_path)])
        self.assertEqual(code, 0)
        self.assertIn("**Decision: ASSIST**", out.getvalue())

    @patch("agent_economics.kimi_analyst._call_kimi_analyst")
    def test_json_output_and_out_file(self, mock_call) -> None:
        mock_call.return_value = KIMI_PAYLOAD
        out_path = Path(self.tmp.name) / "analysis.json"
        with (
            patch.dict(os.environ, {"MOONSHOT_API_KEY": "sk-test"}, clear=True),
            redirect_stdout(StringIO()),
            redirect_stderr(StringIO()),
        ):
                code = main(
                    [
                        "analyse",
                        "--case", str(self.case_path),
                        "--format", "json",
                        "--out", str(out_path),
                    ]
                )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out_path.read_text())["decision"], "ASSIST")

    def test_missing_case_file_exits_two_without_a_traceback(self) -> None:
        err = StringIO()
        with (
            patch.dict(os.environ, {"MOONSHOT_API_KEY": "sk-test"}, clear=True),
            redirect_stdout(StringIO()),
            redirect_stderr(err),
        ):
                code = main(["analyse", "--case", str(Path(self.tmp.name) / "missing.json")])
        self.assertEqual(code, 2)
        self.assertIn("Error:", err.getvalue())

    def test_missing_api_key_exits_two(self) -> None:
        err = StringIO()
        with (
            patch.dict(os.environ, {}, clear=True),
            redirect_stdout(StringIO()),
            redirect_stderr(err),
        ):
                code = main(["analyse", "--case", str(self.case_path)])
        self.assertEqual(code, 2)
        self.assertIn("MOONSHOT_API_KEY", err.getvalue())

    @patch("agent_economics.kimi_analyst._call_kimi_analyst")
    def test_module_entry_point_matches_the_cli(self, mock_call) -> None:
        mock_call.return_value = KIMI_PAYLOAD
        out = StringIO()
        with (
            patch.dict(os.environ, {"MOONSHOT_API_KEY": "sk-test"}, clear=True),
            redirect_stdout(out),
            redirect_stderr(StringIO()),
        ):
                code = _main(["--case", str(self.case_path)])
        self.assertEqual(code, 0)
        self.assertIn("**Decision: ASSIST**", out.getvalue())


class PublicApiIntrospectionTest(unittest.TestCase):
    """
    Regression lock: the annotations on the public API must resolve at runtime.

    These were previously string literals with no module-level import, so
    typing.get_type_hints() raised NameError for any consumer that introspects
    the signatures (Sphinx autodoc, pydantic, runtime validators).
    """

    def test_public_signatures_resolve(self) -> None:
        for fn in (analyse, analyse_report, _build_context_from_case):
            with self.subTest(fn=fn.__name__):
                self.assertTrue(typing.get_type_hints(fn))


if __name__ == "__main__":
    unittest.main()
