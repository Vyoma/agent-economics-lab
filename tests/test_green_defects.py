"""The green-defect corpus, and the published claim that rests on it.

The claim is that every catalogued defect was live at a commit where the whole
suite passed. It is checked by `make green-defects`, which checks out those
commits and runs them. These tests guard the shape of the artifact and the
numbers quoted from it, so a stale figure fails rather than drifts.
"""

from __future__ import annotations

import pathlib
import re
import unittest

from research.green_defects import DEFECTS

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _distinct_total(text: str) -> int:
    """Sum the tests-passing column once per distinct commit."""
    by_commit = {}
    for commit, count in re.findall(r"\| `([0-9a-f]{7})` \| (\d+) \|", text):
        by_commit[commit] = int(count)
    return sum(by_commit.values())
REPORT = ROOT / "research" / "GREEN_DEFECTS.md"


class TheCorpusIsWellFormed(unittest.TestCase):
    def test_every_defect_states_why_no_test_expressed_it(self) -> None:
        """The invisibility field is the contribution. An empty one is a gap."""
        for defect in DEFECTS:
            with self.subTest(defect=defect.id):
                self.assertGreater(len(defect.invisibility), 60)
                self.assertGreater(len(defect.mechanism), 60)

    def test_ids_are_unique(self) -> None:
        ids = [d.id for d in DEFECTS]
        self.assertEqual(len(ids), len(set(ids)))


class ThePublishedNumbersMatchTheReport(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(REPORT.exists(), "run `make green-defects`")
        self.text = REPORT.read_text(encoding="utf-8")

    def test_every_defect_appears(self) -> None:
        for defect in DEFECTS:
            with self.subTest(defect=defect.id):
                self.assertIn(defect.id, self.text)

    def test_the_headline_counts_the_whole_corpus(self) -> None:
        match = re.search(
            r"\*\*(\d+) of (\d+) defects were live at a commit where the "
            r"entire suite passed\.\*\* They sit at (\d+) distinct commits, "
            r"totalling ([\d,]+) passing tests",
            self.text,
        )
        self.assertIsNotNone(match, "headline sentence missing or reworded")
        green, total, _commits, tests = match.groups()
        self.assertEqual(int(total), len(DEFECTS))
        self.assertEqual(
            int(green), len(DEFECTS),
            "a defect was live at a commit whose suite was red; the corpus "
            "claim does not hold for it and the entry must be removed or "
            "the claim narrowed",
        )
        # Was `> 2000`, which required the double-counted 2275 the README
        # calls an error. The distinct total is the sum over distinct commits.
        self.assertEqual(
            int(tests.replace(",", "")),
            _distinct_total(self.text),
            "the headline must sum distinct commits, not the column",
        )

    def test_every_probe_discriminated(self) -> None:
        """A probe that reports the same thing before and after found nothing."""
        pairs = re.findall(
            r"- while live: `(.+?)`\n  - after the fix: `(.+?)`", self.text
        )
        self.assertEqual(len(pairs), len(DEFECTS))
        for live, fixed in pairs:
            with self.subTest(live=live[:40]):
                self.assertNotEqual(live, fixed)

    def test_the_readme_summary_matches_the_generated_report(self) -> None:
        """The front page keeps the conclusion; the report keeps the table."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        rows = re.findall(r"\| `([0-9a-f]{7})` \| (\d+) \|", self.text)
        commits = {commit for commit, _count in rows}
        words = {3: "three", 5: "Five"}
        expected = (
            f"{words[len(DEFECTS)]} defects were live across "
            f"{words[len(commits)]} green commits. The distinct suite total "
            f"was {_distinct_total(self.text)} tests"
        )
        self.assertIn(expected, " ".join(readme.split()))
        self.assertIn("not the previously reported 2275", readme)
        self.assertIn("case series, not a rate", readme)

    def test_the_population_limit_is_stated(self) -> None:
        """A case series presented as a rate would be the thing this repo is against."""
        self.assertIn("case series, not a rate", self.text)


if __name__ == "__main__":
    unittest.main()
