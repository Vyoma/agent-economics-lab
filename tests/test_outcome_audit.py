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

from research.outcome_audit import AUDIT, _summarise, render

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "research" / "OUTCOME_AUDIT.md"


class TheFrozenEvidenceIsWellFormed(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(AUDIT.read_text(encoding="utf-8"))

    def test_it_pins_the_upstream_revision(self) -> None:
        self.assertRegex(self.document["upstream"]["revision"], r"^[0-9a-f]{40}$")

    def test_every_row_carries_a_trajectory_digest(self) -> None:
        """Without it a reader cannot confirm a row against the source."""
        for arm, rows in self.document["arms"].items():
            with self.subTest(arm=arm):
                self.assertTrue(rows)
                for row in rows:
                    self.assertRegex(row["trajectory_sha256"], r"^[0-9a-f]{64}$")

    def test_no_arm_is_recorded_empty(self) -> None:
        """A rate-limited download is not evidence of a zero result."""
        for arm, rows in self.document["arms"].items():
            with self.subTest(arm=arm):
                self.assertGreater(len(rows), 0)

    def test_it_holds_no_prompt_or_response_content(self) -> None:
        allowed = {
            "task_id", "resolved", "scores_resolved",
            "api_calls", "instance_cost_usd", "trajectory_sha256",
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
        for arm, summary in self.arms.items():
            rows = [
                line for line in self.readme.splitlines()
                if line.startswith(f"| `{arm}` | {summary['n']} |")
            ]
            with self.subTest(arm=arm):
                self.assertTrue(rows, f"README has no audit row for {arm}")
                naive = f"{summary['naive_rate']:.1%}"
                unknown = str(summary["unknown"])
                confirmed = (
                    f"{summary['confirmed_rate']:.1%}"
                    if summary["confirmed_rate"] is not None
                    else "unestablished"
                )
                self.assertTrue(
                    any(
                        naive in row and confirmed in row
                        and f"| {unknown} |" in row
                        for row in rows
                    ),
                    f"no README audit row for {arm} carries {naive}, "
                    f"{unknown} unknown and {confirmed}; found {rows}",
                )

    def test_the_headline_spend_and_call_count_match(self) -> None:
        summary = self.arms["gemini-3-pro"]
        self.assertIn(f"${summary['spend_usd']:,.2f}", self.readme)
        self.assertIn(f"{summary['api_calls']:,} API calls", self.readme)
