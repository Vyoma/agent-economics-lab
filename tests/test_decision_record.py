from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path

from agent_economics.adapters import load_normalized_json_bundle
from agent_economics.cli import main
from agent_economics.decision_record import (
    GATE_ENTRY_POINT,
    SCHEMA_VERSION,
    blank_decision_record,
    load_decision_record,
    render_blank_decision_record,
    render_decision_record_html,
    validate_decision_record,
    verify_decision_record,
)
from agent_economics.provenance import Attestation

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agent-decision-record.json"
BUNDLE = ROOT / "examples" / "agent-decision-record.bundle.json"
ATTESTATIONS = ROOT / "examples" / "attestations.json"
TEMPLATE = ROOT / "templates" / "agent-decision-record.template.json"
SCHEMA = ROOT / "templates" / "agent-decision-record.schema.json"
HTML_EXAMPLE = ROOT / "examples" / "agent-decision-record.html"


def _attestations() -> dict[str, Attestation]:
    raw = json.loads(ATTESTATIONS.read_text(encoding="utf-8"))
    return {
        name: Attestation(instrument=name, **fields)
        for name, fields in raw.items()
    }


class DecisionRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.bundle = load_normalized_json_bundle(BUNDLE)

    def verify(self, document: object) -> tuple[str, ...]:
        return verify_decision_record(
            document,
            bundle=self.bundle,
            artifact_root=ROOT,
            bundle_ref="examples/agent-decision-record.bundle.json",
            attestations=_attestations(),
            attestation_ref="examples/attestations.json",
        )

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
        self.assertEqual(
            schema["properties"]["assurance"]["properties"]["gate_entry_point"][
                "const"
            ],
            GATE_ENTRY_POINT,
        )

    def test_filled_example_is_structurally_valid(self) -> None:
        self.assertEqual(validate_decision_record(self.example), ())

    def test_filled_example_recomputes_end_to_end(self) -> None:
        self.assertEqual(self.verify(self.example), ())

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "decision-record",
                    "validate",
                    str(EXAMPLE),
                    "--bundle",
                    str(BUNDLE),
                    "--attestations",
                    str(ATTESTATIONS),
                    "--artifact-root",
                    str(ROOT),
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertIn("VERIFIED", output.getvalue())
        self.assertIn("decision=ASSIST", output.getvalue())

    def test_checked_in_html_matches_the_record_renderer(self) -> None:
        self.assertEqual(
            HTML_EXAMPLE.read_text(encoding="utf-8"),
            render_decision_record_html(self.example),
        )
        self.assertIn(
            "Verified against supplied artifacts",
            render_decision_record_html(self.example),
        )
        self.assertIn(
            "real-world truth or representativeness",
            render_decision_record_html(self.example),
        )

    def test_renderer_escapes_record_text(self) -> None:
        record = deepcopy(self.example)
        record["workload"]["name"] = '<script>alert("not markup")</script>'
        rendered = render_decision_record_html(record)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_cli_renders_only_after_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "decision-record.html"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "decision-record",
                        "render",
                        str(EXAMPLE),
                        "--bundle",
                        str(BUNDLE),
                        "--attestations",
                        str(ATTESTATIONS),
                        "--artifact-root",
                        str(ROOT),
                        "--output",
                        str(target),
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                render_decision_record_html(self.example),
            )
            self.assertIn("Wrote VERIFIED", output.getvalue())

            tampered = deepcopy(self.example)
            tampered["decision"]["issued"] = "STOP"
            tampered_path = Path(directory) / "tampered.json"
            tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
            refused_target = Path(directory) / "tampered.html"
            error = io.StringIO()
            with redirect_stderr(error):
                refused_exit = main(
                    [
                        "decision-record",
                        "render",
                        str(tampered_path),
                        "--bundle",
                        str(BUNDLE),
                        "--attestations",
                        str(ATTESTATIONS),
                        "--artifact-root",
                        str(ROOT),
                        "--output",
                        str(refused_target),
                    ]
                )
            self.assertEqual(refused_exit, 2)
            self.assertFalse(refused_target.exists())
            self.assertIn("decision.issued does not reproduce", error.getvalue())

    def test_verifier_rejects_a_tampered_evidence_digest(self) -> None:
        record = deepcopy(self.example)
        record["evidence"]["evidence_digest"] = "0" * 64
        errors = self.verify(record)
        self.assertTrue(
            any("evidence.evidence_digest does not reproduce" in error for error in errors)
        )

    def test_verifier_rejects_a_tampered_artifact_digest(self) -> None:
        record = deepcopy(self.example)
        record["evidence"]["artifacts"][0]["sha256"] = "0" * 64
        errors = self.verify(record)
        self.assertTrue(
            any("artifact digest mismatch" in error for error in errors)
        )

    def test_verifier_rejects_a_relabelled_decision(self) -> None:
        record = deepcopy(self.example)
        record["decision"]["issued"] = "STOP"
        errors = self.verify(record)
        self.assertTrue(
            any("decision.issued does not reproduce" in error for error in errors)
        )

    def test_verifier_rejects_a_relabelled_claim(self) -> None:
        record = deepcopy(self.example)
        record["claims"][0]["status"] = "PASS"
        errors = self.verify(record)
        self.assertTrue(
            any("claims[0].status does not reproduce" in error for error in errors)
        )

    def test_verifier_rejects_a_relabelled_audit(self) -> None:
        record = deepcopy(self.example)
        record["assurance"]["audit_assessable"] = False
        record["assurance"]["audit_grounds"] = ["unattested instruments"]
        errors = self.verify(record)
        self.assertTrue(
            any("assurance.audit_assessable does not reproduce" in error for error in errors)
        )
        self.assertTrue(
            any("assurance.audit_grounds does not reproduce" in error for error in errors)
        )

    def test_verifier_requires_the_declared_attestation_artifact(self) -> None:
        errors = verify_decision_record(
            self.example,
            bundle=self.bundle,
            artifact_root=ROOT,
            bundle_ref="examples/agent-decision-record.bundle.json",
            attestations=None,
            attestation_ref=None,
        )
        self.assertIn(
            "record declares attestations but no attestation artifact was supplied",
            errors,
        )
        self.assertTrue(
            any("assurance.audit_assessable does not reproduce" in error for error in errors)
        )

    def test_required_claims_must_cover_the_recomputed_contract(self) -> None:
        record = deepcopy(self.example)
        record["claims"][0]["check_id"] = "gate.unregistered@1"
        errors = self.verify(record)
        self.assertTrue(
            any(
                "required claims do not cover the recomputed gate contract" in error
                for error in errors
            )
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

    def test_scale_refuses_an_unassessable_audit(self) -> None:
        record = deepcopy(self.example)
        record["decision"]["issued"] = "SCALE"
        for claim in record["claims"]:
            claim["status"] = "PASS"
        record["uncertainty"]["known_missing_evidence"] = []
        record["assurance"]["audit_assessable"] = False
        record["assurance"]["audit_grounds"] = ["unattested instruments"]
        errors = validate_decision_record(record)
        self.assertIn(
            "decision.issued cannot be SCALE when the audit is unassessable",
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

    def test_artifact_paths_cannot_escape_the_verification_root(self) -> None:
        record = deepcopy(self.example)
        record["evidence"]["artifacts"][0]["uri"] = "../outside.json"
        errors = validate_decision_record(record)
        self.assertIn(
            "evidence.artifacts[0].uri must be a normalized relative path "
            "without '..'",
            errors,
        )

    def test_unknown_fields_are_rejected(self) -> None:
        record = deepcopy(self.example)
        record["decision"]["confidence"] = 0.99
        self.assertIn(
            "decision.confidence is not part of agent-decision-record/v1",
            validate_decision_record(record),
        )

    def test_duplicate_json_keys_are_rejected_before_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(
                '{"schema_version":"agent-decision-record/v1",'
                '"schema_version":"agent-decision-record/v1"}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                load_decision_record(path)

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
