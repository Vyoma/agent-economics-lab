from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from agent_economics import (
    Decision,
    evaluate_bundle,
    load_conversion_contract,
    make_evidence_bundle,
    normalized_json_bundle,
    otel_genai_bundle,
    otel_genai_conversion_contract_template,
    otel_genai_conversion_receipt,
    render_normalized_json,
)
from agent_economics.cli import main
from agent_economics.otel_genai import (
    SEMCONV_GENAI_COMMIT,
    SEMCONV_VERSION,
    inspect_otel_genai_json,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "otel-genai"
LANGFUSE = EXAMPLE / "langfuse-otlp.json"
LANGFUSE_CONTRACT = EXAMPLE / "langfuse-conversion-contract.json"
ARIZE = EXAMPLE / "arize-openinference-otlp.json"
ARIZE_CONTRACT = EXAMPLE / "arize-openinference-conversion-contract.json"


def _write_document(path: Path, document: dict[str, object]) -> None:
    path.write_text(
        json.dumps(document, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


class OtelGenAIAdapterTests(unittest.TestCase):
    def test_two_independent_platform_fixtures_share_one_adapter(self) -> None:
        langfuse = inspect_otel_genai_json(LANGFUSE)
        arize = inspect_otel_genai_json(ARIZE)
        self.assertEqual(langfuse.scopes, ("pydantic-ai@1.0.0",))
        self.assertEqual(
            arize.scopes,
            ("@arizeai/openinference-instrumentation@1.0.0",),
        )
        self.assertEqual(len(langfuse.spans), 2)
        self.assertEqual(len(langfuse.dependency_edges), 1)
        self.assertEqual(len(arize.spans), 1)

    def test_pinned_semantic_contract_is_exposed_in_template(self) -> None:
        template = otel_genai_conversion_contract_template(
            inspect_otel_genai_json(LANGFUSE)
        )
        self.assertEqual(
            template["adapter"]["semantic_conventions_version"],
            SEMCONV_VERSION,
        )
        self.assertEqual(
            template["adapter"]["semantic_conventions_genai_commit"],
            SEMCONV_GENAI_COMMIT,
        )

    def test_content_firewall_discards_messages_and_tool_arguments(self) -> None:
        session = inspect_otel_genai_json(LANGFUSE)
        contract = load_conversion_contract(LANGFUSE_CONTRACT)
        bundle = otel_genai_bundle(LANGFUSE, contract)
        rendered = render_normalized_json(
            bundle,
            conversion=otel_genai_conversion_receipt(
                session, contract, bundle
            ),
        )
        self.assertNotIn("CONTENT_FIREWALL_SENTINEL", rendered)
        self.assertNotIn("gen_ai.input.messages", rendered)
        self.assertNotIn("gen_ai.tool.call.arguments", rendered)

    def test_content_fields_are_not_decoded_but_duplicate_keys_fail(self) -> None:
        source = json.loads(LANGFUSE.read_text(encoding="utf-8"))
        attributes = source["resourceSpans"][0]["scopeSpans"][0]["spans"][0][
            "attributes"
        ]
        content = next(
            row for row in attributes if row["key"] == "gen_ai.input.messages"
        )
        content["value"] = {"notAnOtelAnyValue": "still private"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unread-content.json"
            _write_document(path, source)
            self.assertEqual(len(inspect_otel_genai_json(path).spans), 2)

        source = json.loads(ARIZE.read_text(encoding="utf-8"))
        attributes = source["resourceSpans"][0]["scopeSpans"][0]["spans"][0][
            "attributes"
        ]
        attributes.append(copy.deepcopy(attributes[0]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate-attribute.json"
            _write_document(path, source)
            with self.assertRaisesRegex(ValueError, "duplicate attribute"):
                inspect_otel_genai_json(path)

    def test_completed_fixtures_emit_scale_and_preserve_parentage(self) -> None:
        langfuse = otel_genai_bundle(
            LANGFUSE, load_conversion_contract(LANGFUSE_CONTRACT)
        )
        arize = otel_genai_bundle(
            ARIZE, load_conversion_contract(ARIZE_CONTRACT)
        )
        self.assertEqual(evaluate_bundle(langfuse).decision, Decision.SCALE)
        self.assertEqual(evaluate_bundle(arize).decision, Decision.SCALE)
        self.assertEqual(len(langfuse.dependency_edges), 1)
        self.assertEqual(arize.dependency_edges, ())

    def test_unknown_price_and_unapproved_task_mapping_fail_closed(self) -> None:
        contract = load_conversion_contract(LANGFUSE_CONTRACT)
        del contract["pricing"]["tools"]["retrieve"]
        with self.assertRaisesRegex(
            ValueError, "must exactly match the observed source tools"
        ):
            otel_genai_bundle(LANGFUSE, contract)

        contract = load_conversion_contract(LANGFUSE_CONTRACT)
        contract["task_mapping"]["approved_by"] = None
        with self.assertRaisesRegex(ValueError, "approved_by"):
            otel_genai_bundle(LANGFUSE, contract)

    def test_source_inventory_and_task_identity_are_frozen(self) -> None:
        contract = load_conversion_contract(ARIZE_CONTRACT)
        contract["source_inventory"]["span_count"] = 2
        with self.assertRaisesRegex(
            ValueError, "does not match the frozen OTLP JSON"
        ):
            otel_genai_bundle(ARIZE, contract)

        contract = load_conversion_contract(ARIZE_CONTRACT)
        contract["tasks"][0]["trace_id_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "trace_id_sha256"):
            otel_genai_bundle(ARIZE, contract)

    def test_unsupported_operation_and_unresolved_parent_fail_closed(self) -> None:
        source = json.loads(ARIZE.read_text(encoding="utf-8"))
        attributes = source["resourceSpans"][0]["scopeSpans"][0]["spans"][0][
            "attributes"
        ]
        operation = next(
            row for row in attributes if row["key"] == "gen_ai.operation.name"
        )
        operation["value"]["stringValue"] = "invoke_agent"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsupported.json"
            _write_document(path, source)
            with self.assertRaisesRegex(ValueError, "Unsupported economic"):
                inspect_otel_genai_json(path)

        source = json.loads(LANGFUSE.read_text(encoding="utf-8"))
        source["resourceSpans"][0]["scopeSpans"][0]["spans"][1][
            "parentSpanId"
        ] = "ffffffffffffffff"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unresolved-parent.json"
            _write_document(path, source)
            with self.assertRaisesRegex(ValueError, "unresolved parentSpanId"):
                inspect_otel_genai_json(path)

    def test_normalized_receipt_detects_dependency_edge_tampering(self) -> None:
        session = inspect_otel_genai_json(LANGFUSE)
        contract = load_conversion_contract(LANGFUSE_CONTRACT)
        bundle = otel_genai_bundle(LANGFUSE, contract)
        document = json.loads(
            render_normalized_json(
                bundle,
                conversion=otel_genai_conversion_receipt(
                    session, contract, bundle
                ),
            )
        )
        document["dependency_edges"] = []
        with self.assertRaisesRegex(
            ValueError, "evidence_digest does not match"
        ):
            normalized_json_bundle(document)

    def test_cycle_diagnostic_warns_without_changing_scale(self) -> None:
        original = otel_genai_bundle(
            ARIZE, load_conversion_contract(ARIZE_CONTRACT)
        )
        event_id = original.events[0].event_id
        bundle = make_evidence_bundle(
            events=original.events,
            outcomes=original.outcomes,
            rates=original.rates,
            baseline=original.baseline,
            policy=original.policy,
            source_id=original.source_id,
            source_version=original.source_version,
            task_manifest=original.task_manifest,
            dependency_edges=((event_id, event_id),),
        )
        case = evaluate_bundle(bundle)
        self.assertEqual(case.decision, Decision.SCALE)
        self.assertEqual(case.findings[0].control, "directed_dependency_cycle")

    def test_cli_template_convert_and_evaluate_round_trip(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template.json"
            bundle = root / "bundle.json"
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                template_exit = main(
                    [
                        "convert",
                        "--from",
                        "otel-genai",
                        "--in",
                        str(LANGFUSE),
                        "--template",
                        str(template),
                    ]
                )
                convert_exit = main(
                    [
                        "convert",
                        "--from",
                        "otel-genai",
                        "--in",
                        str(LANGFUSE),
                        "--contract",
                        str(LANGFUSE_CONTRACT),
                        "--out",
                        str(bundle),
                    ]
                )
                evaluate_exit = main(
                    ["evaluate", "--bundle", str(bundle), "--ci"]
                )
        self.assertEqual(template_exit, 0)
        self.assertEqual(convert_exit, 0)
        self.assertEqual(evaluate_exit, 0)


if __name__ == "__main__":
    unittest.main()
