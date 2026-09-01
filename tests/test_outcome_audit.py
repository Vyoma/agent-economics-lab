"""The upstream outcome audit, and the numbers it publishes.

One arm of a public agent-trajectory dataset reports `info.resolved: true` on
all 500 SWE-bench Verified tasks while its own `info.scores.resolved` is the
string `"unknown"` on all 500. Real runs, real spend, unscored outcomes, and a
field left at its default.

The dataset is not at fault: it ships the cross-check that reveals this. A
consumer reading one field and publishing a rate is.
"""

from __future__ import annotations

import json
import pathlib
import re
import unittest

from research.outcome_audit import AUDIT, _summarise, duplicate_arms, render

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "research" / "OUTCOME_AUDIT.md"


class TheFrozenEvidenceIsWellFormed(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(AUDIT.read_text(encoding="utf-8"))

    def test_it_pins_the_upstream_revision(self) -> None:
        self.assertRegex(self.document["upstream"]["revision"], r"^[0-9a-f]{40}$")

    def test_every_row_carries_both_digests(self) -> None:
        """The file hash confirms a row against the source. The transcript hash
        is what makes two arms sharing runs detectable: the model label lives in
        the same file, so their file hashes differ while the runs are the same.
        """
        for arm, rows in self.document["arms"].items():
            with self.subTest(arm=arm):
                self.assertTrue(rows)
                for row in rows:
                    self.assertRegex(row["trajectory_sha256"], r"^[0-9a-f]{64}$")
                    self.assertRegex(row["messages_sha256"], r"^[0-9a-f]{64}$")

    def test_no_arm_is_recorded_empty(self) -> None:
        """A rate-limited download is not evidence of a zero result."""
        for arm, rows in self.document["arms"].items():
            with self.subTest(arm=arm):
                self.assertGreater(len(rows), 0)

    def test_it_holds_no_prompt_or_response_content(self) -> None:
        # An allowlist, not a denylist: a new field must be named here before
        # it can ship, which is what caught `messages_sha256` being added.
        # Both hashes are digests of content, never content.
        allowed = {
            "task_id", "resolved", "scores_resolved",
            "api_calls", "instance_cost_usd", "trajectory_sha256",
            "messages_sha256",
        }
        for arm, rows in self.document["arms"].items():
            for row in rows:
                with self.subTest(arm=arm, task=row["task_id"]):
                    self.assertEqual(set(row), allowed)


class TheFinding(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(AUDIT.read_text(encoding="utf-8"))
        self.arms = {
            arm: _summarise(rows) for arm, rows in self.document["arms"].items()
        }

    def test_exactly_one_arm_has_no_confirmed_rate(self) -> None:
        unscored = [a for a, s in self.arms.items() if s["confirmed_rate"] is None]
        self.assertEqual(unscored, ["gemini-3-pro"])

    def test_that_arm_reads_one_hundred_percent_naively(self) -> None:
        """The number a consumer reading one field would publish."""
        summary = self.arms["gemini-3-pro"]
        self.assertEqual(summary["naive_resolved"], summary["n"])
        self.assertEqual(summary["naive_rate"], 1.0)
        self.assertEqual(summary["unknown"], summary["n"])
        self.assertEqual(summary["scored"], 0)

    def test_the_duplicate_arm_pair_is_detected(self) -> None:
        """Two arms publishing one set of runs, and the label scored twice."""
        pairs = duplicate_arms(self.document)
        self.assertEqual(len(pairs), 1, "expected exactly one duplicated pair")
        pair = pairs[0]
        self.assertEqual(set(pair["arms"]), {"gpt-5.2-codex", "gpt-5.2-high"})
        self.assertEqual(pair["n"], 500)
        self.assertGreater(pair["disagree"], 0)
        self.assertAlmostEqual(
            pair["agreement"], (pair["n"] - pair["disagree"]) / pair["n"]
        )

    def test_the_self_agreement_is_below_the_spread_between_models(self) -> None:
        """The reason the duplication matters.

        If the label agreed with itself perfectly, a few-point model gap would
        mean something. It does not, so gaps of that size cannot be read.
        """
        pair = duplicate_arms(self.document)[0]
        rates = [
            s["confirmed_rate"] for s in self.arms.values()
            if s["confirmed_rate"] is not None
        ]
        disagreement = 1 - pair["agreement"]
        self.assertGreater(disagreement, 0.0)
        self.assertLess(
            disagreement, max(rates) - min(rates),
            "if self-disagreement exceeded the whole spread, no arm could be "
            "compared to any other and the table should not be published",
        )

    def test_the_scored_arms_have_plausible_rates(self) -> None:
        """A guard on the guard: if these ever read 100% the audit is broken."""
        for arm, summary in self.arms.items():
            if summary["confirmed_rate"] is None:
                continue
            with self.subTest(arm=arm):
                self.assertGreater(summary["confirmed_rate"], 0.3)
                self.assertLess(summary["confirmed_rate"], 0.95)

    def test_the_published_page_matches_what_regenerates(self) -> None:
        self.assertEqual(
            PAGE.read_text(encoding="utf-8"), render(self.document) + "\n",
            "run `make outcome-audit`",
        )

    def test_the_page_states_what_the_finding_is_not(self) -> None:
        """An audit of someone else's data must bound its own claim."""
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn("not a claim that the dataset is wrong", text)
        self.assertIn("not a claim about any model's real capability", text)
        self.assertIn("rate-limited", text)

    def test_the_headline_count_matches_the_arms(self) -> None:
        text = PAGE.read_text(encoding="utf-8")
        match = re.search(r"\*\*(\d+) of (\d+) arms examined", text)
        self.assertIsNotNone(match)
        unscored, total = (int(g) for g in match.groups())
        self.assertEqual(total, len(self.arms))
        self.assertEqual(
            unscored,
            sum(1 for s in self.arms.values() if s["confirmed_rate"] is None),
        )


if __name__ == "__main__":
    unittest.main()


class TheReadmeCopyMatchesTheComputation(unittest.TestCase):
    """A hand-typed copy of a computed value is an unguarded claim.

    The README carries this finding as its own table. That table was published
    unguarded first: changing 100.0% to 99.0% failed nothing, which is the
    defect this project exists to refuse, committed in the commit that
    publishes the finding.
    """

    def setUp(self) -> None:
        document = json.loads(AUDIT.read_text(encoding="utf-8"))
        self.arms = {arm: _summarise(rows) for arm, rows in document["arms"].items()}
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_every_audited_arm_appears_with_its_recomputed_figures(self) -> None:
        """Cells compared by position, not by substring.

        The substring form passed while the naive column read 99.9%, because
        `naive` and `confirmed` are the same string for most arms and the
        confirmed cell satisfied the check for both. A guard that cannot tell
        two columns apart is not guarding either.
        """
        for arm, summary in self.arms.items():
            rows = [
                [cell.strip() for cell in line.strip().strip("|").split("|")]
                for line in self.readme.splitlines()
                if line.startswith(f"| `{arm}` |")
            ]
            expected = [
                f"`{arm}`",
                str(summary["n"]),
                f"{summary['naive_rate']:.1%}",
                str(summary["unknown"]),
                (
                    f"{summary['confirmed_rate']:.1%}"
                    if summary["confirmed_rate"] is not None
                    else "**unestablished**"
                ),
            ]
            with self.subTest(arm=arm):
                self.assertTrue(rows, f"README has no audit row for {arm}")
                self.assertIn(
                    expected, rows,
                    f"no README row for {arm} matches {expected} cell for cell; "
                    f"found {rows}",
                )

    def test_the_headline_spend_and_call_count_match(self) -> None:
        summary = self.arms["gemini-3-pro"]
        self.assertIn(f"${summary['spend_usd']:,.2f}", self.readme)
        self.assertIn(f"{summary['api_calls']:,} API calls", self.readme)
