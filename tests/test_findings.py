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
from corpus_report import (  # noqa: E402
    FROZEN,
    nebius_openhands_summary,
    nebius_sweagent_summary,
    readjudication,
    swesmith_summary,
)

AUDIT = ROOT / "examples" / "public-swebench" / "outcome_audit.json"


def _wilson(successes: int, trials: int, z: float = 1.959964) -> tuple[float, float]:
    """Two-sided Wilson interval on a proportion."""
    import math

    if not trials:
        return 0.0, 1.0
    p = successes / trials
    centre = p + z * z / (2 * trials)
    spread = z * math.sqrt(
        p * (1 - p) / trials + z * z / (4 * trials * trials)
    )
    denominator = 1 + z * z / trials
    return (centre - spread) / denominator, (centre + spread) / denominator


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
        # A point estimate quoted from the index without its interval is the
        # failure this corpus keeps finding in other people's numbers.
        low, high = _wilson(len(b) - disagreements, len(b))
        self.assertAlmostEqual(published["self_agreement_low"], low, places=3)
        self.assertAlmostEqual(published["self_agreement_high"], high, places=3)
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
        # The decision figure carries its interval, and the entry asserts
        # that interval excludes zero. If it stops excluding zero the claim
        # that the proxy is reliably worse than the baseline is wrong.
        self.assertAlmostEqual(published["gap_low"], summary["gap_low"], places=2)
        self.assertAlmostEqual(published["gap_high"], summary["gap_high"], places=2)
        self.assertLess(summary["gap_high"], 0)

    def test_009_and_010_the_posttrainbench_figures(self) -> None:
        from corpus_report import posttrainbench_summary

        summary = posttrainbench_summary()
        nine = _figures("AEL-2026-009")
        self.assertAlmostEqual(nine["pooled"], summary["pooled_difference"], places=3)
        self.assertAlmostEqual(
            nine["stratified"], summary["stratified_difference"], places=3
        )
        for key in ("pooled_low", "pooled_high",
                    "stratified_low", "stratified_high"):
            self.assertAlmostEqual(nine[key], summary[key], places=3)
        # The published claim is that stratifying moves the effect onto an
        # interval containing zero, so if it ever stops containing zero the
        # entry is wrong and this must fail rather than let the prose stand.
        self.assertLessEqual(summary["stratified_low"], 0)
        self.assertGreaterEqual(summary["stratified_high"], 0)
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
        from corpus_report import cogym_summary

        summary = cogym_summary()
        pair = summary["pairs"]["outcomeRating|agentRating"]
        eleven = _figures("AEL-2026-011")
        self.assertAlmostEqual(eleven["qwk_low"], pair["qwk_low"], places=3)
        self.assertAlmostEqual(eleven["qwk_high"], pair["qwk_high"], places=3)
        # The entry says the interval straddles the floor, so if it stops
        # straddling, the sentence is wrong.
        self.assertLess(pair["qwk_low"], 0.60)
        self.assertGreater(pair["qwk_high"], 0.60)
        self.assertEqual(eleven["n"], pair["n"])
        self.assertAlmostEqual(eleven["qwk"], pair["qwk"], places=3)
        self.assertAlmostEqual(eleven["exact"], pair["exact"], places=3)

        twelve = _figures("AEL-2026-012")
        self.assertEqual(twelve["rows"], summary["rows"])
        for key, field in (("outcome", "outcomeRating"),
                           ("agent", "agentRating"),
                           ("communication", "communicationRating")):
            self.assertEqual(twelve[key], summary["coverage"][field])

    def test_013_the_hle_verifier_replication(self) -> None:
        from corpus_report import hle_verifier_summary

        summary = hle_verifier_summary()
        published = _figures("AEL-2026-013")
        self.assertEqual(published["questions"], summary["questions"])
        self.assertEqual(published["responses"], summary["responses"])
        self.assertEqual(published["graders"], len(summary["graders"]))
        self.assertAlmostEqual(published["worst_auc"], summary["worst"]["auc"], places=3)
        self.assertAlmostEqual(published["best_auc"], summary["best"]["auc"], places=3)
        self.assertEqual(
            published["intervals_containing_chance"],
            sum(1 for g in summary["graders"]
                if g["indistinguishable_from_random"]),
        )
        # The published claim is that no grader clears the floor, so if one
        # ever does the entry is wrong and this must fail rather than let
        # the prose stand.
        self.assertLess(summary["best"]["auc"], 0.75)

    def test_014_the_unauditable_training_set(self) -> None:
        from corpus_report import openr1_math_summary

        summary = openr1_math_summary()
        published = _figures("AEL-2026-014")
        for key in ("rows", "dual_signal_rows", "symbolic_only_rows",
                    "selection_violations", "admitted_on_judge_alone"):
            self.assertEqual(published[key], summary[key], key)
        self.assertAlmostEqual(
            published["judge_acceptance_rate"],
            summary["judge_acceptance_rate"], places=3,
        )
        verdicts = summary["answer_check"]["verdicts"]
        self.assertEqual(published["verified_sample"], sum(verdicts.values()))
        self.assertEqual(
            published["both_numeric_and_differ"],
            verdicts["both_numeric_and_differ"],
        )
        # The entry rests on the judge having run only where the symbolic
        # check found nothing. If that ever stops holding, the columns
        # become comparable and this is a different finding, so it fails
        # here rather than letting the published prose stand.
        self.assertEqual(summary["selection_violations"], 0)
        # And on correctness_count tracking each signal exactly, not
        # approximately: the provenance claim is an identity or it is
        # nothing.
        self.assertEqual(
            summary["count_tracks_judge"], summary["dual_signal_rows"]
        )
        self.assertEqual(
            summary["count_tracks_symbolic"], summary["symbolic_only_rows"]
        )
        self.assertAlmostEqual(
            _figures("AEL-2026-014")["acceptance_low"],
            summary["acceptance_ci"][0], places=3,
        )
        self.assertAlmostEqual(
            _figures("AEL-2026-014")["acceptance_high"],
            summary["acceptance_ci"][1], places=3,
        )

    def test_the_selection_guard_fires_on_doctored_evidence(self) -> None:
        """Non-vacuous against the evidence rather than the registry: flip
        one symbolic bit on a row that carries both columns, and the
        selection claim the whole entry rests on must stop holding."""
        from unittest import mock

        import corpus_report

        document = corpus_report._load("openr1-math")
        for row in document["rows"]:
            if row["judge"] is not None and not row["misaligned"]:
                row["symbolic"][0] = True
                break
        else:
            self.fail("no dual-signal row to doctor")
        with mock.patch.object(corpus_report, "_load", lambda slug: document):
            self.assertGreater(
                corpus_report.openr1_math_summary()["selection_violations"], 0
            )

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

    def test_every_finding_names_a_check_a_limit_and_an_action(self) -> None:
        """A finding with no command is an assertion; a finding with no
        scope is an overclaim waiting to be quoted out of context; a finding
        with no action is a fact filed for the record."""
        for finding in findings_module.load()["findings"]:
            with self.subTest(finding=finding["id"]):
                self.assertTrue(finding["verify"].strip())
                self.assertGreater(len(finding["scope"]), 40)
                # A finding that never says what to do about it is a fact
                # filed for the record. Fourteen shipped that way before
                # anyone noticed the index had no such field at all.
                self.assertGreater(len(finding["action"]), 30)
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

    def test_every_finding_has_a_recomputation_test(self) -> None:
        """AEL-2026-013's test was written below `unittest.main()`, where
        Python parses it, never binds it to the class, and never runs it.
        The suite reported OK on 15 tests while the newest entry's published
        figures were checked by nothing, in a file whose docstring promises
        every figure recomputes. A method name is the only evidence that a
        figure is actually recomputed, so the names are checked against the
        index rather than trusted."""
        import re

        covered: set[str] = set()
        for name in dir(EveryPublishedFigureRecomputes):
            if name.startswith("test_"):
                covered.update(re.findall(r"\d{3}", name))
        missing = sorted(
            finding["id"] for finding in findings_module.load()["findings"]
            if finding["id"].rsplit("-", 1)[1] not in covered
        )
        self.assertEqual(missing, [], "findings with no recomputation test")

    def test_prose_dataset_counts_match_the_index(self) -> None:
        """PATTERNS.md said "Eight datasets" while the corpus held ten, and
        ROADMAP.md said eight too. PATTERNS.md is generated and byte-compared,
        which caught nothing, because the count was typed into the generator's
        prose and so both sides went stale together. Counted here against the
        index instead of trusted to a build that compares a file with itself."""
        import re

        expected = len({
            f["dataset"] for f in findings_module.load()["findings"]
        })
        words = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
            "twelve": 12,
        }
        for name in ("research/PATTERNS.md", "ROADMAP.md", "research/CORPUS.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            # Only phrasings that denote the corpus total. A sub-count such
            # as "three datasets record two outcome signals" is a different
            # quantity and is computed by its own generator.
            for match in re.finditer(
                r"\b(\w+)\s+(?:audited|public)\s+datasets\b"
                r"|\b(\w+)\s+datasets, chosen partly\b", text, re.I
            ):
                token = (match.group(1) or match.group(2)).lower()
                value = words.get(token, int(token) if token.isdigit() else None)
                if value is None or value > 20:
                    continue
                with self.subTest(file=name, phrase=match.group(0)):
                    self.assertEqual(
                        value, expected,
                        f"{name} says {match.group(0)!r}; the index has "
                        f"{expected} datasets",
                    )

    def test_the_page_recomputes(self) -> None:
        committed = (ROOT / "research" / "FINDINGS.md").read_text(encoding="utf-8")
        self.assertEqual(committed, findings_module.render())


if __name__ == "__main__":
    unittest.main()
