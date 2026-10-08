from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path

from agent_economics.assurance import evaluate_bundle
from agent_economics.cli import main
from agent_economics.decision_record import (
    SCHEMA_VERSION,
    blank_decision_record,
    render_blank_decision_record,
    validate_decision_record,
)
from agent_economics.io import load_csv_bundle


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agent-decision-record.json"
TEMPLATE = ROOT / "templates" / "agent-decision-record.template.json"
SCHEMA = ROOT / "templates" / "agent-decision-record.schema.json"


class DecisionRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_checked_in_template_matches_cli_template(self) -> None:
        checked_in = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(checked_in, blank_decision_record())
        self.assertEqual(
            render_blank_decision_record(),
            json.dumps(checked_in, indent=2, ensure_ascii=False) + "\n",
        )

    def test_schema_and_template_share_the_same_root_contract(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            SCHEMA_VERSION,
        )
        self.assertEqual(set(schema["required"]), set(blank_decision_record()))

    def test_filled_example_is_valid(self) -> None:
        self.assertEqual(validate_decision_record(self.example), ())

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["decision-record", "validate", str(EXAMPLE)])
        self.assertEqual(exit_code, 0)
        self.assertIn("decision=ASSIST", output.getvalue())

    def test_filled_example_binds_the_checked_in_evidence(self) -> None:
        for artifact in self.example["evidence"]["artifacts"]:
            content = (ROOT / artifact["uri"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), artifact["sha256"])

        evidence = load_csv_bundle(
            traces=ROOT / "examples" / "support_trace.csv",
            outcomes=ROOT / "examples" / "outcomes.csv",
            rates=ROOT / "examples" / "rates.json",
            baseline=ROOT / "examples" / "baseline.json",
            policy=ROOT / "examples" / "policy.json",
        )
        case = evaluate_bundle(evidence)
        self.assertEqual(
            evidence.digest,
            self.example["evidence"]["evidence_digest"],
        )
        self.assertEqual(
            case.decision_contract_digest,
            self.example["evidence"]["decision_contract_digest"],
        )

    def test_scale_requires_every_required_claim_to_pass(self) -> None:
        record = deepcopy(self.example)
        record["decision"]["issued"] = "SCALE"
        errors = validate_decision_record(record)
        self.assertIn(
            "decision.issued cannot be SCALE unless every required claim passes",
            errors,
        )

    def test_scale_refuses_known_missing_evidence(self) -> None:
        record = deepcopy(self.example)
        record["decision"]["issued"] = "SCALE"
        for claim in record["claims"]:
            claim["status"] = "PASS"
        errors = validate_decision_record(record)
        self.assertIn(
            "decision.issued cannot be SCALE while known_missing_evidence is non-empty",
            errors,
        )

    def test_incomplete_claim_requires_a_missing_reason(self) -> None:
        record = deepcopy(self.example)
        record["claims"][0]["status"] = "INCOMPLETE"
        record["claims"][0].pop("observed")
        errors = validate_decision_record(record)
        self.assertIn(
            "claims[0].missing_reason is required when status is INCOMPLETE",
            errors,
        )

    def test_claims_cannot_cite_undeclared_artifacts(self) -> None:
        record = deepcopy(self.example)
        record["claims"][0]["evidence_refs"] = ["results/not-registered.json"]
        errors = validate_decision_record(record)
        self.assertIn(
            "claims[0].evidence_refs contains undeclared artifact "
            "'results/not-registered.json'",
            errors,
        )

    def test_unknown_fields_are_rejected(self) -> None:
        record = deepcopy(self.example)
        record["decision"]["confidence"] = 0.99
        self.assertIn(
            "decision.confidence is not part of agent-decision-record/v1",
            validate_decision_record(record),
        )

    def test_init_writes_blank_once_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "decision-record.json"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    ["decision-record", "init", "--output", str(target)]
                )
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                render_blank_decision_record(),
            )

            error = io.StringIO()
            with redirect_stderr(error):
                second_exit_code = main(
                    ["decision-record", "init", "--output", str(target)]
                )
            self.assertEqual(second_exit_code, 2)
            self.assertIn("already exists", error.getvalue())


if __name__ == "__main__":
    unittest.main()
