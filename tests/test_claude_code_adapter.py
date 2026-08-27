from __future__ import annotations

import copy
import csv
import io
import json
import math
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from agent_economics import (
    Decision,
    claude_code_bundle,
    conversion_contract_template,
    conversion_receipt,
    evaluate_bundle,
    inspect_claude_code_jsonl,
    load_normalized_json_bundle,
    load_outcomes,
    load_traces,
    make_evidence_bundle,
    normalized_json_bundle,
    render_normalized_json,
)
from agent_economics.cli import main
from agent_economics.report import render_markdown

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "claude-code"
SESSION = EXAMPLE / "session.jsonl"
CONTRACT = EXAMPLE / "conversion-contract.json"


def _completed_contract(path: Path) -> dict[str, object]:
    session = inspect_claude_code_jsonl(path)
    contract = conversion_contract_template(session)
    contract["outcome_contract"] = {
        "label_source": "fixture.manual-review",
        "rubric_version": "fixture.acceptable-task@1",
    }
    for row in contract["tasks"]:
        assert isinstance(row, dict)
        acceptable = row["started_at"] == "2026-07-17T16:00:00.000Z"
        row.update(
            {
                "acceptable": acceptable,
                "business_value_usd": 10.0 if acceptable else 0.0,
                "human_minutes": 0.5 if acceptable else 2.0,
                "remediation_cost_usd": 0.0 if acceptable else 0.5,
                "incident_loss_usd": 0.0,
            }
        )
    pricing = contract["pricing"]
    assert isinstance(pricing, dict)
    pricing["price_card_id"] = "fixture.explicit-rates@2026-07-17"
    models = pricing["models"]
    assert isinstance(models, dict)
    for model_contract in models.values():
        assert isinstance(model_contract, dict)
        tiers = model_contract["tiers"]
        assert isinstance(tiers, list)
        for tier in tiers:
            assert isinstance(tier, dict)
            tier["input_per_million_usd"] = 3.0
            tier["output_per_million_usd"] = 15.0
            tier["cache_read_per_million_usd"] = 0.3
            cache_rates = tier["cache_write_per_million_usd"]
            assert isinstance(cache_rates, dict)
            for bucket in cache_rates:
                cache_rates[bucket] = 6.0 if "1h" in bucket else 3.75
    tools = pricing["tools"]
    assert isinstance(tools, dict)
    for tool in tools:
        tools[tool] = 0.0
    server_tools = pricing["server_tools"]
    assert isinstance(server_tools, dict)
    for tool in server_tools:
        server_tools[tool] = 0.01
    contract["baseline"] = {
        "acceptable_rate": 0.5,
        "cost_per_attempt_usd": 6.0,
        "name": "illustrative human-only workflow",
        "value_per_acceptable_outcome_usd": 10.0,
    }
    contract["policy"] = {
        "human_hourly_cost_usd": 60.0,
        "max_calls_per_task": 5,
        "max_cost_per_acceptable_outcome_usd": 4.0,
        "max_p95_task_cost_usd": 6.0,
        "max_trace_cost_per_task_usd": 3.0,
        "min_acceptable_rate": 0.75,
        "min_expected_net_value_per_attempt_usd": 0.0,
        "min_incremental_net_value_vs_baseline_usd": 0.0,
        "repetition_warning_threshold": 3,
    }
    return contract


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


class ClaudeCodeAdapterTests(unittest.TestCase):
    def test_template_is_private_and_deduplicates_stream_fragments(self) -> None:
        session = inspect_claude_code_jsonl(SESSION)
        self.assertEqual(len(session.tasks), 2)
        self.assertEqual(len(session.model_calls), 4)
        self.assertEqual(len(session.tool_calls), 2)
        self.assertEqual(len(session.dependency_edges), 4)
        self.assertEqual(session.relevant_record_count, 9)
        rendered = json.dumps(
            conversion_contract_template(session), sort_keys=True
        )
        for secret in (
            "SECRET_PROMPT",
            "SECRET_RESPONSE",
            "SECRET_THINKING",
            "SECRET_TOOL_RESULT",
            "SUPERSECRET",
            "/secret/customer.txt",
            "session-example-001",
            "message-alpha-1",
            "tool-alpha-read",
        ):
            self.assertNotIn(secret, rendered)

    def test_completed_contract_emits_assist_with_source_manifest(self) -> None:
        bundle = claude_code_bundle(SESSION, _completed_contract(SESSION))
        case = evaluate_bundle(bundle)
        self.assertEqual(bundle.source_manifest_id, "source.claude-code-jsonl@1")
        self.assertEqual(len(bundle.events), 6)
        self.assertEqual(len(bundle.dependency_edges), 4)
        self.assertEqual(case.decision, Decision.ASSIST)
        self.assertEqual(case.acceptable_rate, 0.5)
        self.assertEqual(case.breaches, ("acceptable_rate 50.0% < 75.0%",))

    def test_cache_and_server_tool_costs_are_explicit(self) -> None:
        bundle = claude_code_bundle(SESSION, _completed_contract(SESSION))
        model_costs = {
            event.timestamp: event.direct_cost_usd
            for event in bundle.events
            if event.event_type == "model"
        }
        self.assertAlmostEqual(
            model_costs["2026-07-17T16:00:01.000Z"], 0.00162
        )
        self.assertAlmostEqual(
            model_costs["2026-07-17T16:01:03.000Z"], 0.01081
        )

    def test_pricing_tiers_are_selected_by_total_input(self) -> None:
        contract = _completed_contract(SESSION)
        model_contract = contract["pricing"]["models"]["claude-test"]
        standard = copy.deepcopy(model_contract["tiers"][0])
        standard["up_to_input_tokens"] = 500
        elevated = copy.deepcopy(standard)
        elevated["up_to_input_tokens"] = None
        elevated["input_per_million_usd"] = 6.0
        elevated["output_per_million_usd"] = 30.0
        elevated["cache_read_per_million_usd"] = 0.6
        elevated["cache_write_per_million_usd"] = {
            "ephemeral_1h_input_tokens": 12.0,
            "ephemeral_5m_input_tokens": 7.5,
        }
        model_contract["tiers"] = [standard, elevated]
        bundle = claude_code_bundle(SESSION, contract)
        model_costs = {
            event.timestamp: event.direct_cost_usd
            for event in bundle.events
            if event.event_type == "model"
        }
        self.assertAlmostEqual(
            model_costs["2026-07-17T16:00:01.000Z"], 0.00162
        )
        self.assertAlmostEqual(
            model_costs["2026-07-17T16:01:01.000Z"], 0.00213
        )

    def test_billing_context_drift_fails_closed(self) -> None:
        contract = _completed_contract(SESSION)
        context = contract["pricing"]["models"]["claude-test"][
            "billing_contexts"
        ][0]
        context["service_tier"] = "different-tier"
        with self.assertRaisesRegex(
            ValueError, "billing_contexts must exactly match"
        ):
            claude_code_bundle(SESSION, contract)

    def test_source_row_order_does_not_change_economic_digest(self) -> None:
        rows = [
            json.loads(line)
            for line in SESSION.read_text(encoding="utf-8").splitlines()
        ]
        with tempfile.TemporaryDirectory() as directory:
            reordered = Path(directory) / "reordered.jsonl"
            _write_jsonl(reordered, list(reversed(rows)))
            first = claude_code_bundle(SESSION, _completed_contract(SESSION))
            second = claude_code_bundle(
                reordered, _completed_contract(reordered)
            )
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(
            evaluate_bundle(first).breaches, evaluate_bundle(second).breaches
        )

    def test_streamed_usage_uses_the_complete_cumulative_variant(self) -> None:
        rows = [
            json.loads(line)
            for line in SESSION.read_text(encoding="utf-8").splitlines()
        ]
        rows[1]["message"]["usage"]["output_tokens"] = 2
        rows[1]["message"]["usage"].pop("speed", None)
        rows[2]["message"]["usage"]["speed"] = "standard"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "cumulative.jsonl"
            _write_jsonl(source, rows)
            session = inspect_claude_code_jsonl(source)
            first_call = next(
                call
                for call in session.model_calls
                if call.source_message_id == "message-alpha-1"
            )
        self.assertEqual(first_call.usage["output_tokens"], 50)
        self.assertEqual(
            first_call.usage["billing_context"]["speed"],
            "standard",
        )

    def test_streamed_usage_cannot_change_input_accounting(self) -> None:
        rows = [
            json.loads(line)
            for line in SESSION.read_text(encoding="utf-8").splitlines()
        ]
        rows[1]["message"]["usage"]["input_tokens"] = 101
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "inconsistent-input.jsonl"
            _write_jsonl(source, rows)
            with self.assertRaisesRegex(
                ValueError,
                "inconsistent input_tokens",
            ):
                inspect_claude_code_jsonl(source)

    def test_equivalent_csv_rows_produce_the_same_digest_and_decision(self) -> None:
        bundle = claude_code_bundle(SESSION, _completed_contract(SESSION))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            traces = root / "traces.csv"
            outcomes = root / "outcomes.csv"
            with traces.open("w", newline="", encoding="utf-8") as handle:
                fieldnames = [
                    "task_id",
                    "event_id",
                    "timestamp",
                    "event_type",
                    "name",
                    "model",
                    "input_tokens",
                    "output_tokens",
                    "direct_cost_usd",
                    "status",
                    "arguments",
                ]
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for event in reversed(bundle.events):
                    writer.writerow(
                        {
                            **{
                                field: getattr(event, field)
                                for field in fieldnames
                                if field != "arguments"
                            },
                            "arguments": json.dumps(
                                event.arguments, sort_keys=True
                            ),
                        }
                    )
            with outcomes.open("w", newline="", encoding="utf-8") as handle:
                fieldnames = [
                    "task_id",
                    "acceptable",
                    "business_value_usd",
                    "human_minutes",
                    "remediation_cost_usd",
                    "incident_loss_usd",
                ]
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for outcome in reversed(tuple(bundle.outcomes.values())):
                    writer.writerow(
                        {
                            field: getattr(outcome, field)
                            for field in fieldnames
                        }
                    )
            csv_bundle = make_evidence_bundle(
                events=load_traces(traces),
                outcomes=load_outcomes(outcomes),
                rates=bundle.rates,
                baseline=bundle.baseline,
                policy=bundle.policy,
                source_id="source.csv",
                task_manifest=bundle.task_manifest,
                dependency_edges=bundle.dependency_edges,
                declared_delegations=bundle.declared_delegations,
                label_source=bundle.label_source,
            )
        self.assertEqual(bundle.digest, csv_bundle.digest)
        self.assertEqual(
            evaluate_bundle(bundle).decision,
            evaluate_bundle(csv_bundle).decision,
        )
        self.assertEqual(
            evaluate_bundle(bundle).breaches,
            evaluate_bundle(csv_bundle).breaches,
        )

    def test_duplicate_tool_ids_fail_fast(self) -> None:
        rows = [
            json.loads(line)
            for line in SESSION.read_text(encoding="utf-8").splitlines()
        ]
        rows[6]["message"]["content"][0]["id"] = "tool-alpha-read"
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "duplicate-tool.jsonl"
            _write_jsonl(invalid, rows)
            with self.assertRaisesRegex(ValueError, "Duplicate tool use IDs"):
                inspect_claude_code_jsonl(invalid)

    def test_duplicate_outcome_task_ids_fail_fast(self) -> None:
        contract = _completed_contract(SESSION)
        contract["tasks"].append(copy.deepcopy(contract["tasks"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate outcome task ID"):
            claude_code_bundle(SESSION, contract)

    def test_non_finite_economics_fail_fast(self) -> None:
        contract = _completed_contract(SESSION)
        contract["tasks"][0]["human_minutes"] = math.nan
        with self.assertRaisesRegex(ValueError, "must be finite"):
            claude_code_bundle(SESSION, contract)

    def test_normalized_loader_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "duplicate-key.json"
            invalid.write_text(
                '{"events": [], "events": []}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                load_normalized_json_bundle(invalid)

    def test_unknown_tool_cost_fails_closed(self) -> None:
        contract = _completed_contract(SESSION)
        del contract["pricing"]["tools"]["Read"]
        with self.assertRaisesRegex(
            ValueError, "must exactly match observed client tools"
        ):
            claude_code_bundle(SESSION, contract)

    def test_frozen_source_inventory_cannot_silently_change(self) -> None:
        contract = _completed_contract(SESSION)
        contract["source_inventory"]["model_call_count"] = 3
        with self.assertRaisesRegex(ValueError, "does not match the frozen JSONL"):
            claude_code_bundle(SESSION, contract)

    def test_missing_tool_result_fails_closed(self) -> None:
        rows = [
            json.loads(line)
            for line in SESSION.read_text(encoding="utf-8").splitlines()
        ]
        rows[7]["message"]["content"] = []
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "missing-result.jsonl"
            _write_jsonl(invalid, rows)
            with self.assertRaisesRegex(
                ValueError, "must have exactly one tool result"
            ):
                inspect_claude_code_jsonl(invalid)

    def test_tool_result_cannot_cross_task_boundaries(self) -> None:
        rows = [
            json.loads(line)
            for line in SESSION.read_text(encoding="utf-8").splitlines()
        ]
        rows[7]["parentUuid"] = "assistant-alpha-tool"
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "cross-task-result.jsonl"
            _write_jsonl(invalid, rows)
            with self.assertRaisesRegex(
                ValueError, "crosses task boundaries"
            ):
                inspect_claude_code_jsonl(invalid)

    def test_unexpanded_delegation_cannot_be_priced_as_a_free_tool(self) -> None:
        rows = [
            json.loads(line)
            for line in SESSION.read_text(encoding="utf-8").splitlines()
        ]
        rows[6]["message"]["content"][0]["name"] = "Agent"
        with tempfile.TemporaryDirectory() as directory:
            delegated = Path(directory) / "delegated.jsonl"
            _write_jsonl(delegated, rows)
            contract = _completed_contract(delegated)
            with self.assertRaisesRegex(
                ValueError, "nested model calls may be absent"
            ):
                claude_code_bundle(delegated, contract)

    def test_zero_usage_api_error_placeholder_is_not_a_model_call(self) -> None:
        rows = [
            json.loads(line)
            for line in SESSION.read_text(encoding="utf-8").splitlines()
        ]
        api_error = {
            "isApiErrorMessage": True,
            "isSidechain": False,
            "message": {
                "content": [
                    {
                        "text": "SECRET_API_ERROR",
                        "type": "text",
                    }
                ],
                "id": "synthetic-api-error",
                "model": "<synthetic>",
                "role": "assistant",
                "stop_reason": "stop_sequence",
                "type": "message",
                "usage": {
                    "cache_creation": {
                        "ephemeral_1h_input_tokens": 0,
                        "ephemeral_5m_input_tokens": 0,
                    },
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "server_tool_use": {
                        "web_fetch_requests": 0,
                        "web_search_requests": 0,
                    },
                    "service_tier": None,
                },
            },
            "parentUuid": "user-alpha",
            "sessionId": "session-example-001",
            "timestamp": "2026-07-17T16:00:00.500Z",
            "type": "assistant",
            "uuid": "api-error-alpha",
            "version": "2.1.212",
        }
        rows[1]["parentUuid"] = "api-error-alpha"
        rows.insert(1, api_error)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "api-error.jsonl"
            _write_jsonl(source, rows)
            session = inspect_claude_code_jsonl(source)
            rendered = json.dumps(
                conversion_contract_template(session),
                sort_keys=True,
            )
        self.assertEqual(session.relevant_record_count, 10)
        self.assertEqual(len(session.model_calls), 4)
        self.assertNotIn("SECRET_API_ERROR", rendered)

    def test_api_error_marker_cannot_hide_billable_usage(self) -> None:
        rows = [
            json.loads(line)
            for line in SESSION.read_text(encoding="utf-8").splitlines()
        ]
        rows[1]["isApiErrorMessage"] = True
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "billable-api-error.jsonl"
            _write_jsonl(source, rows)
            with self.assertRaisesRegex(
                ValueError,
                "contains billable usage",
            ):
                inspect_claude_code_jsonl(source)

    def test_rendered_bundle_discards_prompt_response_and_argument_values(self) -> None:
        contract = _completed_contract(SESSION)
        session = inspect_claude_code_jsonl(SESSION)
        bundle = claude_code_bundle(SESSION, contract)
        rendered = render_normalized_json(
            bundle, conversion=conversion_receipt(session, contract, bundle)
        )
        for secret in (
            "SECRET_PROMPT",
            "SECRET_RESPONSE",
            "SECRET_THINKING",
            "SECRET_TOOL_RESULT",
            "SUPERSECRET",
            "/secret/customer.txt",
            "session-example-001",
            "message-alpha-1",
            "tool-alpha-read",
        ):
            self.assertNotIn(secret, rendered)
        self.assertNotIn('"command"', rendered)
        self.assertNotIn('"file_path"', rendered)
        self.assertIn('"field_count": 2', rendered)
        self.assertIn('"kind": "string"', rendered)

    def test_argument_keys_are_also_inside_the_content_firewall(self) -> None:
        rows = [
            json.loads(line)
            for line in SESSION.read_text(encoding="utf-8").splitlines()
        ]
        rows[2]["message"]["content"][0]["input"][
            "SECRET_DYNAMIC_OBJECT_KEY"
        ] = "ordinary-value"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dynamic-key.jsonl"
            _write_jsonl(source, rows)
            contract = _completed_contract(source)
            session = inspect_claude_code_jsonl(source)
            bundle = claude_code_bundle(source, contract)
            rendered = render_normalized_json(
                bundle,
                conversion=conversion_receipt(session, contract, bundle),
            )
        self.assertNotIn("SECRET_DYNAMIC_OBJECT_KEY", rendered)

    def test_conversion_receipt_detects_normalized_evidence_tampering(self) -> None:
        contract = _completed_contract(SESSION)
        session = inspect_claude_code_jsonl(SESSION)
        bundle = claude_code_bundle(SESSION, contract)
        document = json.loads(
            render_normalized_json(
                bundle, conversion=conversion_receipt(session, contract, bundle)
            )
        )
        document["events"][0]["direct_cost_usd"] += 1.0
        with self.assertRaisesRegex(
            ValueError, "evidence_digest does not match"
        ):
            normalized_json_bundle(document)

    def test_cli_template_convert_and_evaluate_round_trip(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template.json"
            bundle_path = root / "bundle.json"
            with redirect_stdout(output):
                template_exit = main(
                    [
                        "convert",
                        "--from",
                        "claude-code",
                        "--in",
                        str(SESSION),
                        "--template",
                        str(template),
                    ]
                )
                convert_exit = main(
                    [
                        "convert",
                        "--from",
                        "claude-code",
                        "--in",
                        str(SESSION),
                        "--contract",
                        str(CONTRACT),
                        "--out",
                        str(bundle_path),
                    ]
                )
            payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        self.assertEqual(template_exit, 0)
        self.assertEqual(convert_exit, 0)
        self.assertEqual(
            payload["conversion"]["source_id"], "source.claude-code-jsonl"
        )

    def test_cli_does_not_write_output_for_incomplete_contract(self) -> None:
        error = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle.json"
            with redirect_stderr(error):
                exit_code = main(
                    [
                        "convert",
                        "--from",
                        "claude-code",
                        "--in",
                        str(SESSION),
                        "--contract",
                        str(EXAMPLE / "contract-template.json"),
                        "--out",
                        str(output),
                    ]
                )
            self.assertFalse(output.exists())
        self.assertEqual(exit_code, 2)
        self.assertIn("INCOMPLETE: conversion failed", error.getvalue())

    def test_checked_in_artifacts_are_byte_reproducible(self) -> None:
        contract = _completed_contract(SESSION)
        session = inspect_claude_code_jsonl(SESSION)
        bundle = claude_code_bundle(SESSION, contract)
        expected_template = (EXAMPLE / "contract-template.json").read_text(
            encoding="utf-8"
        )
        expected_bundle = (EXAMPLE / "bundle.json").read_text(encoding="utf-8")
        expected_report = (EXAMPLE / "assurance-case.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            json.dumps(
                conversion_contract_template(session),
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            expected_template,
        )
        self.assertEqual(
            render_normalized_json(
                bundle, conversion=conversion_receipt(session, contract, bundle)
            ),
            expected_bundle,
        )
        self.assertEqual(
            render_markdown(evaluate_bundle(bundle)), expected_report
        )


if __name__ == "__main__":
    unittest.main()
