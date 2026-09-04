"""The citable index cannot drift from the evidence it cites.

Every number in research/findings.json is fixed text, so that a citation
does not move under whoever quoted it. Fixed text is exactly what rots: the
register would keep asserting 91.2% long after the evidence said otherwise,
and it would do so in the one place readers are most likely to trust
without checking. These recompute each published figure from the frozen
evidence and fail the build on any disagreement.
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "corpus"))

import findings as findings_module  # noqa: E402
from audit import (  # noqa: E402
    FROZEN,
    nebius_openhands_summary,
    nebius_sweagent_summary,
    readjudication,
    swesmith_summary,
)

AUDIT = ROOT / "examples" / "public-swebench" / "outcome_audit.json"


def _figures(finding_id: str) -> dict:
    registry = findings_module.load()
    return next(
        f for f in registry["findings"] if f["id"] == finding_id
    )["figures"]


class EveryPublishedFigureRecomputes(unittest.TestCase):
    def test_001_the_unconfirmed_arm(self) -> None:
        arms = json.loads(AUDIT.read_text(encoding="utf-8"))["arms"]
        rows = arms["gemini-3-pro"]
        published = _figures("AEL-2026-001")
        self.assertEqual(published["tasks"], len(rows))
        self.assertEqual(
            published["cross_check_unknown"],
            sum(1 for r in rows if isinstance(r["scores_resolved"], str)),
        )
        self.assertAlmostEqual(
            published["naive_rate"],
            sum(1 for r in rows if r["resolved"] is True) / len(rows),
            places=6,
        )
        self.assertEqual(
            published["idle_resolved"],
            sum(
                1 for r in rows
                if (r["api_calls"] or 0) <= 1
                and not (r["instance_cost_usd"] or 0.0)
                and r["resolved"] is True
            ),
        )

    def test_002_the_twin_self_agreement(self) -> None:
        arms = json.loads(AUDIT.read_text(encoding="utf-8"))["arms"]
        a = {r["task_id"]: r["resolved"] for r in arms["gpt-5.2-codex"]}
        b = arms["gpt-5.2-high"]
        disagreements = sum(1 for r in b if a[r["task_id"]] != r["resolved"])
        published = _figures("AEL-2026-002")
        self.assertEqual(published["tasks"], len(b))
        self.assertEqual(published["disagreements"], disagreements)
        self.assertAlmostEqual(
            published["self_agreement"], 1 - disagreements / len(b), places=3
        )
        # The index promised every figure recomputes and this one did not,
        # so it drifted: 21 is the naive-rate spread, 20.6 the confirmed-rate
        # spread the other two documents publish.
        # The confirmed rate restricts numerator and denominator to scored
        # rows. A first draft counted every resolved row over the scored
        # count, which inflates any arm with unscored rows and gave 22.3.
        rates = []
        for rows in arms.values():
            scored = [r for r in rows if not isinstance(r["scores_resolved"], str)]
            if scored:
                rates.append(
                    sum(1 for r in scored if r["resolved"] is True) / len(scored)
                )
        self.assertAlmostEqual(
            published["spread_points"], (max(rates) - min(rates)) * 100, places=1
        )

    def test_003_the_coderforge_clean_bill(self) -> None:
        document = json.loads(
            (FROZEN / "coderforge.json").read_text(encoding="utf-8")
        )
        summary = readjudication(document)
        published = _figures("AEL-2026-003")
        self.assertEqual(published["rows"], len(document["rows"]))
        self.assertEqual(published["parsed"], summary["parsed"])
        self.assertEqual(published["disagreements"], len(summary["disagreements"]))

    def test_004_and_005_the_swesmith_figures(self) -> None:
        smith = swesmith_summary()
        four = _figures("AEL-2026-004")
        self.assertEqual(four["rows"], smith["rows"])
        self.assertEqual(four["cross_repo_groups"], smith["cross_repo_patch_groups"])
        self.assertEqual(four["affected_rows"], smith["cross_repo_patch_rows"])
        self.assertEqual(four["sampled"], smith["check_groups"])
        self.assertEqual(four["nontrivial"], smith["check_nontrivial"])
        self.assertEqual(four["foreign_path_groups"], smith["check_foreign"])

        five = _figures("AEL-2026-005")
        self.assertEqual(
            five["xml_duplicate_rows"], smith["xml_identical_duplicate_rows"]
        )
        self.assertEqual(five["tool_xml_overlap"], smith["tool_xml_overlap"])
        self.assertEqual(five["served_rows"], smith["rows"])

    def test_006_the_unpopulated_label_column(self) -> None:
        document = json.loads(
            (FROZEN / "jetbrains.json").read_text(encoding="utf-8")
        )
        rows = document["rows"]
        published = _figures("AEL-2026-006")
        self.assertEqual(published["rows"], len(rows))
        self.assertEqual(
            published["populated"],
            sum(1 for r in rows if r["outcome"] is not None),
        )

    def test_007_the_sweagent_clean_bill(self) -> None:
        summary = nebius_sweagent_summary()
        published = _figures("AEL-2026-007")
        self.assertEqual(published["rows"], summary["rows"])
        self.assertEqual(published["resolved"], summary["resolved"])
        self.assertEqual(
            published["resolved_empty_patch"], summary["resolved_with_empty_patch"]
        )
        self.assertEqual(
            published["resolved_empty_logs"], summary["resolved_with_empty_logs"]
        )
        self.assertEqual(
            published["duplicate_transcripts"], summary["duplicate_transcript_groups"]
        )

    def test_008_the_generated_test_instrument(self) -> None:
        summary = nebius_openhands_summary()
        published = _figures("AEL-2026-008")
        self.assertEqual(published["n"], summary["cross_present"])
        self.assertAlmostEqual(published["kappa"], summary["kappa"], places=3)
        self.assertEqual(published["valid_n"], summary["valid_n"])
        self.assertAlmostEqual(
            published["valid_kappa"], summary["valid_kappa"], places=3
        )
        self.assertAlmostEqual(
            published["valid_precision"], summary["valid_precision"], places=3
        )
        self.assertAlmostEqual(
            published["invalid_kappa"], summary["invalid_kappa"], places=3
        )

    def test_009_and_010_the_posttrainbench_figures(self) -> None:
        from audit import posttrainbench_summary

        summary = posttrainbench_summary()
        nine = _figures("AEL-2026-009")
        self.assertAlmostEqual(nine["pooled"], summary["pooled_difference"], places=3)
        self.assertAlmostEqual(
            nine["stratified"], summary["stratified_difference"], places=3
        )
        self.assertAlmostEqual(nine["overstatement"], summary["overstatement"], places=1)
        self.assertEqual(
            nine["helps_in"], summary["benchmarks_where_contamination_helps"]
        )

        ten = _figures("AEL-2026-010")
        self.assertEqual(ten["rows"], summary["rows"])
        self.assertEqual(ten["no_metrics_file"], summary["no_metrics_file"])
        self.assertEqual(ten["malformed_metrics"], summary["malformed_metrics"])
        self.assertEqual(ten["unusable"], summary["unusable_accuracy"])
        self.assertEqual(ten["unjudged"], summary["unjudged"])

    def test_011_and_012_the_cogym_figures(self) -> None:
        from audit import cogym_summary

        summary = cogym_summary()
        pair = summary["pairs"]["outcomeRating|agentRating"]
        eleven = _figures("AEL-2026-011")
        self.assertEqual(eleven["n"], pair["n"])
        self.assertAlmostEqual(eleven["qwk"], pair["qwk"], places=3)
        self.assertAlmostEqual(eleven["exact"], pair["exact"], places=3)

        twelve = _figures("AEL-2026-012")
        self.assertEqual(twelve["rows"], summary["rows"])
        for key, field in (("outcome", "outcomeRating"),
                           ("agent", "agentRating"),
                           ("communication", "communicationRating")):
            self.assertEqual(twelve[key], summary["coverage"][field])

    def test_the_recomputation_fires_on_a_doctored_figure(self) -> None:
        """Proven non-vacuous: move one published number, watch it fail."""
        from unittest import mock

        registry = findings_module.load()
        for finding in registry["findings"]:
            if finding["id"] == "AEL-2026-008":
                finding["figures"]["kappa"] = 0.42
        with mock.patch.object(findings_module, "load", lambda: registry):
            with self.assertRaises(AssertionError):
                self.test_008_the_generated_test_instrument()


class TheIndexIsWellFormed(unittest.TestCase):
    def test_identifiers_are_unique_and_dated(self) -> None:
        registry = findings_module.load()
        ids = [f["id"] for f in registry["findings"]]
        self.assertEqual(len(ids), len(set(ids)))
        for finding in registry["findings"]:
            with self.subTest(finding=finding["id"]):
                self.assertRegex(finding["id"], r"^AEL-\d{4}-\d{3}$")
                self.assertRegex(finding["date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_every_finding_names_a_check_and_a_limit(self) -> None:
        """A finding with no command is an assertion; a finding with no
        scope is an overclaim waiting to be quoted out of context."""
        for finding in findings_module.load()["findings"]:
            with self.subTest(finding=finding["id"]):
                self.assertTrue(finding["verify"].strip())
                self.assertGreater(len(finding["scope"]), 40)
                self.assertIn(finding["kind"], findings_module.KIND_LABEL)

    def test_clean_bills_are_present(self) -> None:
        """An index with no clean bills is a complaint log, and its defects
        should be read as such."""
        kinds = [f["kind"] for f in findings_module.load()["findings"]]
        self.assertGreater(kinds.count("clean"), 0)

    def test_every_corpus_dataset_appears(self) -> None:
        corpus = (ROOT / "research" / "CORPUS.md").read_text(encoding="utf-8")
        import re

        datasets = set(
            re.findall(r"https://huggingface\.co/datasets/([\w\-./]+?)\)", corpus)
        )
        indexed = {f["dataset"] for f in findings_module.load()["findings"]}
        self.assertEqual(
            datasets - indexed, set(),
            "a dataset is audited in CORPUS.md but has no findings entry",
        )

    def test_the_page_recomputes(self) -> None:
        committed = (ROOT / "research" / "FINDINGS.md").read_text(encoding="utf-8")
        self.assertEqual(committed, findings_module.render())


if __name__ == "__main__":
    unittest.main()

    def test_013_the_hle_verifier_replication(self) -> None:
        from audit import hle_verifier_summary

        summary = hle_verifier_summary()
        published = _figures("AEL-2026-013")
        self.assertEqual(published["questions"], summary["questions"])
        self.assertEqual(published["responses"], summary["responses"])
        self.assertEqual(published["graders"], len(summary["graders"]))
        self.assertAlmostEqual(published["worst_auc"], summary["worst"]["auc"], places=3)
        self.assertAlmostEqual(published["best_auc"], summary["best"]["auc"], places=3)
        # The published claim is that no grader clears the floor, so if one
        # ever does the entry is wrong and this must fail rather than let
        # the prose stand.
        self.assertLess(summary["best"]["auc"], 0.75)
