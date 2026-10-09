from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path

from agent_economics.feedback_contract import (
    SCHEMA_VERSION,
    blank_feedback_contract,
    feedback_contract_digest,
    load_feedback_contract,
    main,
    render_blank_feedback_contract,
    validate_feedback_contract,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "production-feedback-contract.template.json"
EXAMPLE = ROOT / "examples" / "production-feedback-contract.json"


class FeedbackContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_checked_in_template_matches_the_public_constructor(self) -> None:
        checked_in = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(checked_in, blank_feedback_contract())
        self.assertEqual(
            render_blank_feedback_contract(),
            json.dumps(checked_in, indent=2, ensure_ascii=False) + "\n",
        )
        self.assertEqual(checked_in["schema_version"], SCHEMA_VERSION)

    def test_blank_template_is_intentionally_invalid(self) -> None:
        errors = validate_feedback_contract(blank_feedback_contract())
        self.assertIn("system.modalities must not be empty", errors)
        self.assertIn("interventions must not be empty", errors)
        self.assertIn("non_claims must not be empty", errors)

    def test_filled_cross_modality_example_is_valid_and_executable(self) -> None:
        self.assertEqual(validate_feedback_contract(self.example), ())
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main([str(EXAMPLE)])
        self.assertEqual(exit_code, 0)
        self.assertRegex(output.getvalue(), r"^VALID digest=[0-9a-f]{64}\n$")

    def test_digest_ignores_object_key_order_but_binds_policy(self) -> None:
        reordered = dict(reversed(list(self.example.items())))
        self.assertEqual(
            feedback_contract_digest(self.example),
            feedback_contract_digest(reordered),
        )
        changed = deepcopy(self.example)
        changed["rollout"]["rollback_when"] = "a different rollback condition"
        self.assertNotEqual(
            feedback_contract_digest(self.example),
            feedback_contract_digest(changed),
        )

    def test_declared_modalities_require_exact_evidence_surfaces(self) -> None:
        missing = deepcopy(self.example)
        del missing["modality_evidence"]["predictive"]
        self.assertIn(
            "modality_evidence is missing declared modalities: predictive",
            validate_feedback_contract(missing),
        )

        extra = deepcopy(self.example)
        extra["system"]["modalities"].remove("agent")
        self.assertIn(
            "modality_evidence contains undeclared modalities: agent",
            validate_feedback_contract(extra),
        )

    def test_each_modality_keeps_its_distinct_required_evidence(self) -> None:
        required = {
            "predictive": "calibration",
            "generative": "prompt_version",
            "agent": "side_effect_ledger",
        }
        for modality, field in required.items():
            with self.subTest(modality=modality, field=field):
                changed = deepcopy(self.example)
                del changed["modality_evidence"][modality][field]
                self.assertIn(
                    f"{field}",
                    "\n".join(validate_feedback_contract(changed)),
                )

        changed = deepcopy(self.example)
        changed["modality_evidence"]["generative"]["task_outcome"] = "other"
        self.assertTrue(
            any(
                "generative.task_outcome must name outcome.name" in error
                for error in validate_feedback_contract(changed)
            )
        )

    def test_proxy_must_name_the_primary_outcome_and_its_limits(self) -> None:
        changed = deepcopy(self.example)
        changed["proxies"][0]["validated_against"] = "a_different_outcome"
        errors = validate_feedback_contract(changed)
        self.assertTrue(
            any("validated_against must name outcome.name" in error for error in errors)
        )

        for field in ("failure_modes", "allowed_uses", "forbidden_uses"):
            with self.subTest(field=field):
                changed = deepcopy(self.example)
                changed["proxies"][0][field] = []
                self.assertIn(
                    f"proxies[0].{field} must not be empty",
                    validate_feedback_contract(changed),
                )

    def test_missing_outcome_or_join_routes_cannot_fail_open(self) -> None:
        changed = deepcopy(self.example)
        changed["outcome"]["missing_route"] = "SCALE"
        self.assertTrue(
            any(
                "outcome.missing_route must be one of" in error
                for error in validate_feedback_contract(changed)
            )
        )

        changed = deepcopy(self.example)
        changed["joins"]["unmatched_route"] = "DROP"
        self.assertTrue(
            any(
                "joins.unmatched_route must be one of" in error
                for error in validate_feedback_contract(changed)
            )
        )

    def test_interventions_and_rollout_require_rollback_semantics(self) -> None:
        changed = deepcopy(self.example)
        changed["interventions"][0]["layer"] = "presentation"
        self.assertTrue(
            any(
                "interventions[0].layer must be one of" in error
                for error in validate_feedback_contract(changed)
            )
        )

        changed = deepcopy(self.example)
        changed["rollout"]["rollback_when"] = ""
        self.assertIn(
            "rollout.rollback_when must be a non-empty string",
            validate_feedback_contract(changed),
        )

    def test_contract_requires_explicit_non_claims(self) -> None:
        changed = deepcopy(self.example)
        changed["non_claims"] = []
        self.assertIn(
            "non_claims must not be empty",
            validate_feedback_contract(changed),
        )

    def test_unknown_fields_are_rejected(self) -> None:
        changed = deepcopy(self.example)
        changed["headline_accuracy"] = 0.99
        self.assertIn(
            "unknown field: headline_accuracy",
            validate_feedback_contract(changed),
        )

    def test_loader_rejects_duplicate_keys_and_non_finite_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            duplicate = Path(directory) / "duplicate.json"
            duplicate.write_text(
                '{"schema_version":"a","schema_version":"b"}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                load_feedback_contract(duplicate)

            non_finite = Path(directory) / "non-finite.json"
            non_finite.write_text('{"value":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Non-finite JSON number"):
                load_feedback_contract(non_finite)

    def test_schema_dates_digest_and_cli_fail_closed(self) -> None:
        wrong_schema = deepcopy(self.example)
        wrong_schema["schema_version"] = "production-feedback-contract/v2"
        self.assertIn(
            "schema_version must equal 'production-feedback-contract/v1'",
            validate_feedback_contract(wrong_schema),
        )
        with self.assertRaisesRegex(ValueError, "invalid feedback contract"):
            feedback_contract_digest(wrong_schema)

        bad_date = deepcopy(self.example)
        bad_date["system"]["observation_window"]["end"] = "not-a-date"
        self.assertIn(
            "system.observation_window.end must be an ISO date",
            validate_feedback_contract(bad_date),
        )

        with tempfile.TemporaryDirectory() as directory:
            malformed = Path(directory) / "malformed.json"
            malformed.write_text("{", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main([str(malformed)])
            self.assertEqual(exit_code, 2)
            self.assertTrue(output.getvalue().startswith("INVALID "))


if __name__ == "__main__":
    unittest.main()
