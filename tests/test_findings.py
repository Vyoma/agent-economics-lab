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

    def test_015_abstention_moves_the_baseline_too(self) -> None:
        from corpus_report import openhands_selective_prediction

        summary = openhands_selective_prediction()
        published = _figures("AEL-2026-015")
        full, retained, abstained = (
            summary["full"], summary["retained"], summary["abstained"]
        )
        self.assertEqual(published["full_rows"], full["rows"])
        self.assertEqual(published["retained_rows"], retained["rows"])
        self.assertEqual(published["abstained_rows"], abstained["rows"])
        self.assertEqual(published["draws"], summary["draws"])
        for key, value in (
            ("full_agreement", full["agreement"]),
            ("full_majority", full["majority_baseline"]),
            ("retained_coverage", retained["coverage"]),
            ("retained_agreement", retained["agreement"]),
            ("retained_majority", retained["majority_baseline"]),
            ("retained_always_fail", retained["always_fail_baseline"]),
        ):
            self.assertAlmostEqual(published[key], value, places=4, msg=key)
        for key, value in (
            ("full_gap", full["gap"]),
            ("retained_gap", retained["gap"]),
            ("abstained_gap", abstained["gap"]),
            ("full_gap_low", full["gap_low"]),
            ("full_gap_high", full["gap_high"]),
            ("retained_gap_low", retained["gap_low"]),
            ("retained_gap_high", retained["gap_high"]),
            ("abstained_gap_low", abstained["gap_low"]),
            ("abstained_gap_high", abstained["gap_high"]),
        ):
            self.assertAlmostEqual(published[key], value, places=2, msg=key)
        self.assertAlmostEqual(
            published["adjusted_alpha"], summary["adjusted_alpha"], places=5
        )
        # The claim is that no arm clears its baseline. If a re-freeze ever
        # makes one clear it, this is a different finding and the published
        # prose must fail rather than stand.
        self.assertEqual(published["arms_beating_baseline"], 0)
        self.assertFalse(summary["any_arm_beats_baseline"])
        for one in summary["arms"]:
            self.assertLess(one["gap_high"], 0, one["label"])
        # The entry's whole point is that the majority class flips, which is
        # what makes the raw-accuracy comparison invalid. Assert the flip
        # itself, not only the numbers either side of it.
        self.assertEqual(full["majority_policy"], "always-fail")
        self.assertEqual(retained["majority_policy"], "always-pass")
        # And that the retained accuracy really does look like an improvement
        # in isolation. Without this the finding is about a subset that got
        # worse, which is not interesting and is not what is published.
        self.assertGreater(retained["agreement"], full["agreement"])
        # One implementation of the full-coverage numbers, not two: these
        # must match the entry AEL-2026-008 already published from a
        # separate function over the same evidence.
        eight = nebius_openhands_summary()
        self.assertAlmostEqual(full["agreement"], eight["agreement"], places=6)
        self.assertAlmostEqual(
            full["majority_baseline"], eight["majority_baseline"], places=6
        )
        self.assertEqual(full["rows"], eight["cross_present"])

    def test_016_abstention_widens_faster_than_it_lifts(self) -> None:
        from corpus_report import hle_selective_prediction

        summary = hle_selective_prediction()
        published = _figures("AEL-2026-016")
        self.assertEqual(published["graders"], len(summary["graders"]))
        for key in ("chance_at_full", "chance_at_quarter", "rose_at_quarter",
                    "family", "draws"):
            self.assertEqual(published[key], summary[key], key)
        self.assertEqual(
            published["cleared_at_quarter"], len(summary["cleared_at_quarter"])
        )
        self.assertAlmostEqual(
            published["adjusted_alpha"], summary["adjusted_alpha"], places=6
        )
        by_name = {g["judge"]: g for g in summary["graders"]}
        for judge, prefix in (("gemini-3-flash", "gemini"),
                              ("gpt5.2-high", "gpt52")):
            grader = by_name[judge]
            quarter = grader["levels"][0.25]
            self.assertAlmostEqual(
                published[f"{prefix}_full"], grader["full_auc"], places=4
            )
            for suffix, value in (("quarter", quarter["auc"]),
                                  ("low", quarter["low"]),
                                  ("high", quarter["high"])):
                self.assertAlmostEqual(
                    published[f"{prefix}_{suffix}"], value, places=4,
                    msg=f"{prefix}_{suffix}",
                )
        self.assertAlmostEqual(
            published["gpt52_quarter_spread_rule"],
            by_name["gpt5.2-high"]["levels"][0.25]["by_rule"]["spread"],
            places=3,
        )
        self.assertAlmostEqual(
            published["worst_quarter"],
            min(g["levels"][0.25]["auc"] for g in summary["graders"]),
            places=4,
        )
        # The headline is the direction: more graders sit at chance after
        # abstaining than before, even though most point estimates rose.
        # Both halves have to hold or the entry says something else.
        self.assertGreater(summary["chance_at_quarter"], summary["chance_at_full"])
        self.assertGreater(summary["rose_at_quarter"], summary["chance_at_full"])
        # Exactly the two named in the prose clear chance, by name rather
        # than by count, so a re-freeze that swapped which two cannot pass.
        self.assertEqual(
            summary["cleared_at_quarter"], ["gemini-3-flash", "gpt5.2-high"]
        )
        # The guard that matters is not how many questions tie at the cutoff
        # but how far the tie-break could move the answer. A count threshold
        # was tried here first and was arbitrary: stdev ties 14 questions at
        # 50% coverage and still owns 0.002 of the figure, because those 14
        # carry near-identical AUCs.
        for key, published in (("stdev", "tie_band_stdev"),
                               ("spread", "tie_band_spread"),
                               ("top-margin", "tie_band_top_margin"),
                               ("few-at-top", "tie_band_few_at_top")):
            self.assertAlmostEqual(
                _figures("AEL-2026-016")[published],
                summary["tie_band"][key], places=3, msg=key,
            )
        # The published rule has to stay the one the tie-break cannot swing,
        # by a wide margin over the rules it is being preferred to. If a
        # re-freeze ever closes that gap, the choice of rule stops being
        # defensible and this entry has to be rewritten rather than pass.
        self.assertLess(summary["tie_band"]["stdev"], 0.01)
        self.assertGreater(
            min(summary["tie_band"][r] for r in ("spread", "top-margin")),
            summary["tie_band"]["stdev"] * 100,
        )
        # And the drop the entry attributes to fixing the leak has to be
        # real: the leaking sort read 0.833 where the honest spread rule
        # reads 0.566, so the two must stay far apart.
        self.assertLess(
            by_name["gpt5.2-high"]["levels"][0.25]["by_rule"]["spread"], 0.70
        )

    def test_the_confidence_rules_cannot_see_the_outcome(self) -> None:
        """Non-vacuous against the leak that produced the first draft of
        AEL-2026-016: invert every correctness label and the confidence
        signals must not move at all. A gate that shifts when the answer key
        flips is reading the answer key."""
        from unittest import mock

        import corpus_report

        document = corpus_report._load("hle-verifiers")
        before = [
            corpus_report._confidence(
                [float(v) for v in (row["scores"].get(judge) or [])
                 if v is not None]
            )
            for row in document["rows"]
            for judge in sorted(document["judges"])
            if len([v for v in (row["scores"].get(judge) or [])
                    if v is not None]) >= 2
        ]
        for row in document["rows"]:
            row["correct"] = [not y for y in row["correct"]]
        with mock.patch.object(corpus_report, "_load", lambda slug: document):
            after = [
                corpus_report._confidence(
                    [float(v) for v in (row["scores"].get(judge) or [])
                     if v is not None]
                )
                for row in document["rows"]
                for judge in sorted(document["judges"])
                if len([v for v in (row["scores"].get(judge) or [])
                        if v is not None]) >= 2
            ]
        self.assertEqual(before, after)
        self.assertTrue(before)

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
        """Proven non-vacuous: move one published number, watch it fail.

        One entry was covered here and the guard was assumed to generalise.
        It does not generalise for free: a recomputation test that reads a
        figure it never asserts on passes a doctored registry happily, so
        each entry's own test is doctored rather than one standing in for
        the rest.
        """
        from unittest import mock

        doctored = {
            "AEL-2026-008": ("kappa", 0.42,
                             self.test_008_the_generated_test_instrument),
            "AEL-2026-015": ("retained_gap", 12.5,
                             self.test_015_abstention_moves_the_baseline_too),
            "AEL-2026-016": ("gpt52_quarter", 0.833,
                             self.test_016_abstention_widens_faster_than_it_lifts),
        }
        for identifier, (key, value, check) in doctored.items():
            with self.subTest(finding=identifier, figure=key):
                registry = findings_module.load()
                entry = next(
                    f for f in registry["findings"] if f["id"] == identifier
                )
                self.assertIn(key, entry["figures"])
                entry["figures"][key] = value
                with mock.patch.object(
                    findings_module, "load", lambda r=registry: r
                ):
                    with self.assertRaises(AssertionError):
                        check()


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

    def test_prose_finding_counts_match_the_index(self) -> None:
        """The sibling of the dataset-count guard, added because the same
        drift happened again on a different noun: README.md said the project
        had filed "fourteen results" and that "two of the fourteen" were
        clean bills, and stayed saying it while the index reached sixteen.
        Nothing compared the two, so the front page was the last place to
        find out. Only live phrasings are matched; a sentence about what was
        true when a past defect was found is history and says so."""
        import re

        findings = findings_module.load()["findings"]
        expected = sum(1 for f in findings if f["status"] == "standing")
        clean = sum(
            1 for f in findings
            if f["status"] == "standing" and f["kind"] == "clean"
        )
        words = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
            "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
            "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
            "twenty": 20,
        }

        def number(token: str) -> int | None:
            token = token.lower()
            if token in words:
                return words[token]
            return int(token) if token.isdigit() else None

        for name in ("README.md", "research/PATTERNS.md",
                     "research/CORPUS.md", "docs/contributing-an-audit.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for match in re.finditer(
                r"\bfiled\s+(\w+)\s*\n?\s*results\b"
                r"|\b(?:of|of the)\s+(\w+)\s+are clean bills\b"
                r"|\b(\w+)\s+published findings\b", text, re.I
            ):
                # "six of the fourteen findings published at the time" is a
                # statement about a past state and is not a live count. Any
                # phrasing that dates itself is exempt; one that does not is
                # asserting the present total and has to be right.
                if "at the time" in text[match.end():match.end() + 60]:
                    continue
                value = number(next(g for g in match.groups() if g))
                if value is None:
                    continue
                with self.subTest(file=name, phrase=match.group(0).strip()):
                    self.assertEqual(
                        value, expected,
                        f"{name} says {match.group(0).strip()!r}; the index "
                        f"has {expected} standing findings",
                    )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        stated = re.search(r"\b(\w+)\s+of the \w+ are clean bills", readme)
        self.assertIsNotNone(stated, "README no longer states a clean-bill count")
        self.assertEqual(number(stated.group(1)), clean)

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
