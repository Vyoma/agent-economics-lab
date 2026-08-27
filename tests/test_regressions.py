"""Regression tests for the invariants this release establishes.

Each invariant is easy to lose to an innocuous-looking change, and most of them
fail silently rather than loudly: a digest that stops covering what it claims, a
score that cannot vary, an error that becomes data. Grouped here so the properties
that must hold are readable in one place.

Invariants:
  1  the contract digest covers check implementations, not just declared identity
  2  the mutation score is capable of reporting a failure
  3  the sensitivity grid perturbs one assumption against one construction
  4  the verdict schema stays within Moonshot Flavored JSON Schema
  5  a rejected request aborts rather than becoming a label
  6  the token budget accommodates deep reasoning
  7  every Moonshot credential system is reachable
  8  an unusable key is refused locally
  9  arithmetic that cannot complete produces a typed refusal
  10 the README quotes what the engine actually prints
"""
from __future__ import annotations

import json
import unittest
import urllib.error
from dataclasses import replace
from pathlib import Path

from agent_economics import (
    CheckMode,
    CheckOutput,
    default_checks,
    evaluate_bundle,
    kimi_client,
)
from agent_economics.assurance import decision_contract_digest
from agent_economics.checks import DEFAULT_REQUIRED_COVERAGE
from agent_economics.kimi_judge import _verdict_schema
from false_green import build_evidence, scenario_matrix

ROOT = Path(__file__).resolve().parents[1]

_RUBRIC = json.loads((ROOT / "examples/kimi-judge/rubric.json").read_text())


def _permissive(view):
    return CheckOutput(results=())


class ContractDigestBindsImplementation(unittest.TestCase):
    """The digest must cover what a check does, not only what it declares.

    A gate can keep its ID, version, coverage, and failure route while ceasing to
    enforce anything. Coverage cannot see that substitution, so without an
    implementation fingerprint the contract digest would be byte-identical for an
    enforcing and a permissive gate.
    """

    def test_permissive_substitution_changes_the_digest(self) -> None:
        checks = default_checks()
        baseline = decision_contract_digest(checks, DEFAULT_REQUIRED_COVERAGE)
        gates = [c for c in checks if c.mode is CheckMode.GATE]
        self.assertEqual(len(gates), 6)
        for gate in gates:
            mutated = tuple(
                replace(c, run=_permissive) if c.id == gate.id else c for c in checks
            )
            with self.subTest(gate=gate.id):
                self.assertNotEqual(
                    baseline,
                    decision_contract_digest(mutated, DEFAULT_REQUIRED_COVERAGE),
                )

    def test_manifest_records_a_fingerprint_per_check(self) -> None:
        from agent_economics.assurance import decision_contract_manifest

        manifest = decision_contract_manifest(
            default_checks(), DEFAULT_REQUIRED_COVERAGE
        )
        entries = manifest["checks"]
        assert isinstance(entries, list)
        self.assertTrue(
            all(len(e["implementation_digest"]) == 64 for e in entries)
        )


class FingerprintScopeIsDocumentedHonestly(unittest.TestCase):
    """The fingerprint is not transitive, and the docs must keep saying so.

    It hashes each check's own `run` source, not the helpers `run` calls. All six
    gates route through `checks._result`, so editing that helper changes the
    verdict while leaving the contract digest byte-identical. This was verified by
    executing it. The claim was previously stated as "every check's source is
    hashed into the contract", which is false, so this test guards the corrected
    wording rather than an unstated assumption.
    """

    def test_fingerprint_does_not_cover_called_helpers(self) -> None:
        """Demonstrate the hole directly, so nobody has to trust the prose."""
        from agent_economics import checks as checks_module
        from agent_economics.models import implementation_fingerprint

        gates = [c for c in default_checks() if c.mode is CheckMode.GATE]
        before = {g.id: implementation_fingerprint(g.run) for g in gates}
        baseline = decision_contract_digest(
            default_checks(), DEFAULT_REQUIRED_COVERAGE
        )

        # Swap the shared helper every gate delegates to. No check body changes.
        original = checks_module._result
        try:
            checks_module._result = lambda *a, **k: CheckOutput(results=())
            after = {g.id: implementation_fingerprint(g.run) for g in gates}
            digest = decision_contract_digest(
                default_checks(), DEFAULT_REQUIRED_COVERAGE
            )
        finally:
            checks_module._result = original

        self.assertEqual(before, after, "helper edits leave fingerprints unchanged")
        self.assertEqual(digest, baseline, "and leave the contract digest unchanged")

    def test_the_limitation_is_disclosed_where_it_matters(self) -> None:
        """Every place that describes the fingerprint must state the scope."""
        for name, needle in (
            ("docs/limitations.md", "not transitive"),
            ("README.md", "not transitive"),
            ("docs/landscape.md", "not transitive"),
            ("agent_economics/models.py", "NOT transitive"),
        ):
            with self.subTest(doc=name):
                self.assertIn(needle, (ROOT / name).read_text(encoding="utf-8"))

    def test_no_document_claims_every_source_is_hashed(self) -> None:
        """The specific false sentence must not come back."""
        for name in ("README.md", "docs/limitations.md", "docs/landscape.md",
                     "docs/modularity.md"):
            with self.subTest(doc=name):
                self.assertNotIn(
                    "every check's source is hashed",
                    (ROOT / name).read_text(encoding="utf-8"),
                )


class PercentileIsHonestOnSmallSamples(unittest.TestCase):
    """p95 equals the maximum for any n < 20, which the docs must not obscure.

    `rank = ceil(0.95n)` equals `n` whenever n <= 19, so on the eight-task demo
    fixture the p95 and maximum columns are the same statistic printed twice. That
    is not a coincidence to be read as agreement between two measures.
    """

    def test_p95_equals_max_below_twenty_samples(self) -> None:
        from agent_economics.assurance import percentile

        for n in range(1, 20):
            values = [float(i) for i in range(1, n + 1)]
            with self.subTest(n=n):
                self.assertEqual(percentile(values, 0.95), max(values))

    def test_p95_separates_from_max_at_twenty(self) -> None:
        from agent_economics.assurance import percentile

        values = [float(i) for i in range(1, 21)]
        self.assertNotEqual(percentile(values, 0.95), max(values))

    def test_small_sample_caveat_is_documented(self) -> None:
        text = (ROOT / "docs/limitations.md").read_text(encoding="utf-8")
        self.assertIn("p95", text)
        self.assertIn("fewer than 20", text)


class MutationScoreCanVary(unittest.TestCase):
    """A mutation score must be able to report a failure.

    Gate removal is detected by a fixed coverage contract by construction, so a
    harness that injects only removal reports 100% for every possible input. The
    substitution operator is what gives the number information content.
    """

    def test_substitution_operator_produces_survivors(self) -> None:
        import mutation_score

        rows = mutation_score.run_mutations()
        summary = mutation_score.summarize(rows)
        operators = summary["operators"]
        assert isinstance(operators, dict)
        substitution = operators[mutation_score.SUBSTITUTION]
        self.assertGreater(substitution["fixed_contract_survived"], 0)
        self.assertLess(substitution["fixed_contract_score"], 1.0)
        self.assertEqual(
            substitution["fixed_contract_survived"],
            substitution["dynamic_coverage_survived"],
            "the fixed contract must not be credited with an advantage it lacks",
        )

    def test_forced_result_is_labelled_and_not_sold_as_evidence(self) -> None:
        import mutation_score

        rendered = mutation_score.render_summary(
            mutation_score.summarize(mutation_score.run_mutations())
        )
        self.assertIn("forced", rendered)
        self.assertNotIn("PERFECT", rendered)


class SensitivityGridUsesOneConstruction(unittest.TestCase):
    """A sensitivity grid must perturb one assumption, not swap constructions.

    If the grid builds evidence differently from the baseline it compares against,
    the identity cell disagrees with the unperturbed verdict and flip counts are
    inflated by the difference rather than by the assumption.
    """

    def test_identity_cell_reproduces_the_unperturbed_verdict(self) -> None:
        import sensitivity_sweep

        for scenario in scenario_matrix():
            with self.subTest(scenario=scenario.id):
                self.assertIs(
                    sensitivity_sweep._decision(
                        scenario,
                        incident_loss_usd=scenario.tail_loss_usd,
                        remediation_cost_usd=0.0,
                    ),
                    sensitivity_sweep._decision(scenario),
                )

    def test_overrides_do_not_disturb_the_frozen_matrix(self) -> None:
        """Adding the override parameters must leave published artifacts intact."""
        scenario = scenario_matrix()[0]
        self.assertEqual(
            build_evidence(scenario).digest,
            build_evidence(
                scenario,
                incident_loss_usd=None,
                remediation_cost_usd=None,
                baseline_acceptable_rate=None,
            ).digest,
        )


class SchemaIsMfjsCompatible(unittest.TestCase):
    """The verdict schema must stay inside Moonshot Flavored JSON Schema.

    MFJS accepts only `type`, `enum`, and `required` for validation. A range
    keyword returns HTTP 400, so the schema never reaches the model and, because an
    error becomes an unacceptable label, the failure looks like a 0% acceptable
    rate rather than a rejected request.
    """

    def test_verdict_schema_carries_no_rejected_keyword(self) -> None:
        kimi_client.assert_mfjs_compatible(_verdict_schema(_RUBRIC))
        blob = json.dumps(_verdict_schema(_RUBRIC))
        for keyword in kimi_client.MFJS_REJECTED_KEYWORDS:
            with self.subTest(keyword=keyword):
                self.assertNotIn(f'"{keyword}"', blob)

    def test_bounds_are_enforced_in_code_instead(self) -> None:
        from agent_economics.kimi_judge import _validate_verdict

        criteria = [c["id"] for c in _RUBRIC["criteria"]]
        verdict = {
            "task_id": "t",
            "criterion_scores": {name: 0.5 for name in criteria},
            "overall_score": 0.5,
            "acceptable": True,
            "rationale": "ok",
        }
        _validate_verdict(verdict, _RUBRIC)
        verdict["overall_score"] = 1.7
        with self.assertRaises(ValueError):
            _validate_verdict(verdict, _RUBRIC)


class RejectedRequestIsNotALabel(unittest.TestCase):
    """A rejected request must abort, never become a label.

    `HTTPError` subclasses `URLError`, so a handler that degrades on network
    trouble will also swallow a 400 or 401 and relabel an entire batch from
    requests the model never evaluated.
    """

    def test_non_retryable_status_raises_a_distinct_error(self) -> None:
        from unittest.mock import patch

        for status in (400, 401, 403, 404, 422):
            with self.subTest(status=status):
                with patch.object(
                    kimi_client,
                    "_post",
                    side_effect=urllib.error.HTTPError(
                        kimi_client.API_URL, status, "no", {}, None
                    ),
                ), self.assertRaises(kimi_client.KimiRequestError) as caught:
                    kimi_client.call_kimi("s", "u", api_key="k")
                self.assertEqual(caught.exception.status, status)

    def test_request_error_is_not_a_urlerror_the_judge_swallows(self) -> None:
        error = kimi_client.KimiRequestError(400, "bad schema")
        self.assertNotIsInstance(error, urllib.error.URLError)
        self.assertIsInstance(error, RuntimeError)


class TokenBudgetFitsDeepReasoning(unittest.TestCase):
    """The token budget must accommodate the reasoning it asks for.

    K3 always reasons and reasoning shares the completion budget, so a budget
    sized for a short answer is spent before any content is emitted.
    """

    def test_budgets_exceed_a_shallow_answer_allowance(self) -> None:
        from agent_economics import kimi_analyst, kimi_judge

        self.assertEqual(kimi_client.DEFAULT_REASONING_EFFORT, "max")
        self.assertGreaterEqual(kimi_judge._MAX_COMPLETION_TOKENS, 16384)
        self.assertGreaterEqual(kimi_analyst._MAX_COMPLETION_TOKENS, 16384)

    def test_empty_content_is_an_error_not_a_verdict(self) -> None:
        from unittest.mock import patch

        with patch.object(
            kimi_client,
            "_post",
            return_value={
                "choices": [{"message": {"content": ""}}],
                "usage": {"completion_tokens": 2048},
            },
        ), self.assertRaises(RuntimeError):
            kimi_client.call_kimi("s", "u", api_key="k")


class AllCredentialSystemsReachable(unittest.TestCase):
    """Every Moonshot credential system must be reachable.

    Keys are not interchangeable across the three systems, and Kimi Code uses a
    different path as well as a different host, so a single hardcoded endpoint
    makes valid keys unusable with no configuration remedy.
    """

    def test_each_system_resolves_to_its_documented_route(self) -> None:
        from unittest.mock import patch

        expected = {
            "api.moonshot.ai": "https://api.moonshot.ai/v1/chat/completions",
            "api.moonshot.cn": "https://api.moonshot.cn/v1/chat/completions",
            "api.kimi.com": "https://api.kimi.com/coding/v1/chat/completions",
        }
        self.assertEqual(set(expected), set(kimi_client.KIMI_HOSTS))
        for host, url in expected.items():
            with self.subTest(host=host), patch.dict(
                "os.environ",
                {kimi_client.BASE_URL_ENV_VAR: f"https://{host}"},
            ):
                self.assertEqual(kimi_client.resolve_api_url(), url)

    def test_override_cannot_leave_kimi(self) -> None:
        from unittest.mock import patch

        for hostile in (
            "https://api.openai.com/v1",
            "http://api.moonshot.ai/v1",
            "https://api.moonshot.ai.evil.example/v1",
        ):
            with self.subTest(override=hostile), patch.dict(
                "os.environ", {kimi_client.BASE_URL_ENV_VAR: hostile}
            ), self.assertRaises(ValueError):
                kimi_client.resolve_api_url()


class PlaceholderKeyFailsLocally(unittest.TestCase):
    """An unusable key must be refused locally, with the reason.

    A templated or truncated value cannot authenticate anywhere, so spending
    network calls on it only yields a misleading "credential rejected". The docs
    must also not ship a value that is copy-pasteable as a key.
    """

    def test_documentation_placeholder_is_caught_without_a_request(self) -> None:
        self.assertIsNotNone(kimi_client.api_key_shape_problem("sk-..."))

    def test_docs_no_longer_ship_a_pasteable_fake(self) -> None:
        for name in ("README.md", "docs/kimi-integration.md"):
            with self.subTest(doc=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertNotIn("export MOONSHOT_API_KEY=...", text)

    def test_a_realistic_key_still_passes(self) -> None:
        self.assertIsNone(
            kimi_client.api_key_shape_problem("sk-" + "a1B2c3D4e5" * 5)
        )


class SummedOverflowIsTyped(unittest.TestCase):
    """Arithmetic that cannot complete must produce a typed refusal.

    Individually valid finite costs can sum to an unrepresentable total. A
    fail-closed engine has to answer that with an explained error rather than a
    stdlib traceback.
    """

    def test_overflowing_total_raises_an_explained_valueerror(self) -> None:
        from test_stress_properties import build_bundle

        with self.assertRaises(ValueError) as caught:
            evaluate_bundle(build_bundle(tasks=2, cost=1e308, acceptable=2))
        self.assertNotIsInstance(caught.exception, OverflowError)
        self.assertIn("overflow", str(caught.exception).lower())


class ReadmeMatchesTheEngine(unittest.TestCase):
    """The README must quote what the engine actually prints.

    A recorded image cannot be re-verified when the code changes, so it drifts
    silently while every other published number stays checked in CI.
    """

    def test_no_recorded_terminal_asset_is_cited(self) -> None:
        self.assertFalse((ROOT / "assets/demo.gif").exists())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for pattern in ("demo.gif", ".mp4", ".webm", ".mov"):
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, readme)

    def test_quoted_decision_line_is_what_the_engine_prints(self) -> None:
        from agent_economics import load_csv_bundle
        from agent_economics.report import render_markdown

        examples = ROOT / "examples"
        report = render_markdown(
            evaluate_bundle(
                load_csv_bundle(
                    traces=examples / "support_trace.csv",
                    outcomes=examples / "outcomes.csv",
                    rates=examples / "rates.json",
                    baseline=examples / "baseline.json",
                    policy=examples / "policy.json",
                )
            )
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for line in (
            "**Decision: ASSIST**",
            "| Cost per acceptable outcome | $3.50 |",
            "- **FAIL · gate.tail-cost:** p95_task_cost $14.25 > $8.00",
        ):
            with self.subTest(line=line):
                self.assertIn(line, report)
                self.assertIn(line, readme)


if __name__ == "__main__":
    unittest.main()
